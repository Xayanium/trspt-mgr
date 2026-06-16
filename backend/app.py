from __future__ import annotations

from typing import Any

import pyodbc
from flask import Flask, jsonify, request
from flask_cors import CORS

from config import config
from db import execute_non_query, execute_query, get_connection, insert_and_return_id, rows_to_dicts
from resources import RESOURCES, Resource


app = Flask(__name__)
CORS(app)


def ok(data: Any = None, message: str = "操作成功", status: int = 200):
    return jsonify({"success": True, "message": message, "data": data}), status


def fail(message: str, status: int = 400, detail: str | None = None):
    payload = {"success": False, "message": message}
    if detail:
        payload["detail"] = detail
    return jsonify(payload), status


@app.errorhandler(pyodbc.Error)
def handle_db_error(error: pyodbc.Error):
    return fail("数据库操作失败，请检查输入和 SQL Server 连接", 500, str(error))


@app.errorhandler(Exception)
def handle_error(error: Exception):
    return fail("服务端处理失败", 500, str(error))


def get_resource(name: str) -> Resource:
    if name not in RESOURCES:
        raise KeyError(name)
    return RESOURCES[name]


ADMIN_ROLES = {"系统管理员", "保卫处管理员", "审核员"}
OWNER_ROLE = "车主"
OWNER_RESOURCES = {
    "vehicles",
    "appointments",
    "violations",
    "penalties",
    "appeals",
    "points-additions",
    "scoring-periods",
}


def current_user() -> dict[str, Any] | None:
    user_id = request.headers.get("X-User-Id") or request.args.get("user_id")
    if not user_id:
        return None
    rows = execute_query(
        """
        SELECT user_id, username, real_name, role, department_id, registrant_id, is_active
        FROM dbo.t_user
        WHERE user_id = ? AND is_active = 1;
        """,
        [user_id],
    )
    return rows[0] if rows else None


def is_admin(user: dict[str, Any] | None) -> bool:
    return bool(user and user.get("role") in ADMIN_ROLES)


def is_owner(user: dict[str, Any] | None) -> bool:
    return bool(user and user.get("role") == OWNER_ROLE and user.get("registrant_id") is not None)


def require_user() -> tuple[dict[str, Any] | None, Any | None]:
    user = current_user()
    if not user:
        return None, fail("请先登录", 401)
    return user, None


def require_admin() -> tuple[dict[str, Any] | None, Any | None]:
    user, error = require_user()
    if error:
        return None, error
    if not is_admin(user):
        return None, fail("当前用户无管理员权限", 403)
    return user, None


def clean_payload(payload: dict[str, Any], allowed: tuple[str, ...]) -> tuple[list[str], list[Any]]:
    columns: list[str] = []
    values: list[Any] = []
    for column in allowed:
        if column in payload:
            value = payload[column]
            columns.append(column)
            values.append(None if value == "" else value)
    return columns, values


def build_where(resource: Resource, search: str | None) -> tuple[str, list[Any]]:
    if not search:
        return "", []
    clauses = [f"CONVERT(NVARCHAR(MAX), [{column}]) LIKE ?" for column in resource.searchable]
    params = [f"%{search}%"] * len(clauses)
    return "WHERE " + " OR ".join(clauses), params


def combine_where(parts: list[str]) -> str:
    clauses = [part.strip() for part in parts if part and part.strip()]
    if not clauses:
        return ""
    cleaned = [clause[6:].strip() if clause.upper().startswith("WHERE ") else clause for clause in clauses]
    return "WHERE " + " AND ".join(f"({clause})" for clause in cleaned)


def owner_filter(resource_name: str, user: dict[str, Any]) -> tuple[str, list[Any]]:
    registrant_id = user["registrant_id"]
    if resource_name == "vehicles":
        return "registrant_id = ?", [registrant_id]
    if resource_name == "appointments":
        return """
            (
                vehicle_id IN (SELECT vehicle_id FROM dbo.t_vehicle WHERE registrant_id = ?)
                OR appointer_person_id = ?
            )
        """, [registrant_id, registrant_id]
    if resource_name == "violations":
        return "vehicle_id IN (SELECT vehicle_id FROM dbo.t_vehicle WHERE registrant_id = ?)", [registrant_id]
    if resource_name == "penalties":
        return """
            (
                source_vehicle_id IN (SELECT vehicle_id FROM dbo.t_vehicle WHERE registrant_id = ?)
                OR target_vehicle_id IN (SELECT vehicle_id FROM dbo.t_vehicle WHERE registrant_id = ?)
                OR target_person_id = ?
            )
        """, [registrant_id, registrant_id, registrant_id]
    if resource_name == "appeals":
        return "applicant_id = ?", [registrant_id]
    if resource_name == "points-additions":
        return """
            (
                applicant_id = ?
                OR vehicle_id IN (SELECT vehicle_id FROM dbo.t_vehicle WHERE registrant_id = ?)
            )
        """, [registrant_id, registrant_id]
    if resource_name == "scoring-periods":
        return "vehicle_id IN (SELECT vehicle_id FROM dbo.t_vehicle WHERE registrant_id = ?)", [registrant_id]
    if resource_name == "registration-applications":
        return "applicant_registrant_id = ?", [registrant_id]
    if resource_name == "permits":
        return "vehicle_id IN (SELECT vehicle_id FROM dbo.t_vehicle WHERE registrant_id = ?)", [registrant_id]
    return "1 = 0", []


def resource_access(resource_name: str, user: dict[str, Any]) -> tuple[bool, tuple[str, list[Any]]]:
    if is_admin(user):
        return True, ("", [])
    if is_owner(user) and resource_name in OWNER_RESOURCES:
        return True, owner_filter(resource_name, user)
    return False, ("", [])


@app.get("/api/health")
def health():
    try:
        result = execute_query("SELECT DB_NAME() AS database_name, SYSDATETIME() AS server_time;")
        return ok({"database": result[0]["database_name"], "server_time": result[0]["server_time"]})
    except Exception as error:
        return fail("无法连接 SQL Server，请检查 backend/.env 配置", 503, str(error))


@app.get("/api/resources")
def resources():
    user, error = require_user()
    if error:
        return error
    return ok([
        {"key": key, "title": resource.title, "pk": resource.pk, "columns": resource.columns, "writable": resource.writable}
        for key, resource in RESOURCES.items()
        if resource_access(key, user)[0]
    ])


@app.post("/api/auth/login")
def login():
    payload = request.get_json(force=True) or {}
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""
    if not username or not password:
        return fail("请输入用户名和密码")
    rows = execute_query(
        """
        SELECT user_id, username, password_hash, real_name, role, department_id, registrant_id, is_active
        FROM dbo.t_user
        WHERE username = ? AND is_active = 1;
        """,
        [username],
    )
    if not rows:
        return fail("用户名或密码错误", 401)
    user = rows[0]
    stored = user.pop("password_hash")
    # Coursework demo mode: seed data uses FAKE_HASH_FOR_DEMO_ONLY, accepted with 123456.
    if not (password == stored or (stored == "FAKE_HASH_FOR_DEMO_ONLY" and password == "123456")):
        return fail("用户名或密码错误", 401)
    return ok(user, "登录成功")


@app.get("/api/dashboard")
def dashboard():
    user, error = require_user()
    if error:
        return error
    if is_admin(user):
        sql = """
        SELECT
            (SELECT COUNT(*) FROM dbo.t_vehicle) AS vehicle_count,
            (SELECT COUNT(*) FROM dbo.t_vehicle WHERE register_status = N'正常') AS normal_vehicle_count,
            (SELECT COUNT(*) FROM dbo.t_violation WHERE status <> N'已撤销') AS violation_count,
            (SELECT COUNT(*) FROM dbo.t_penalty WHERE status IN (N'待执行', N'执行中')) AS active_penalty_count,
            (SELECT COUNT(*) FROM dbo.t_appointment WHERE status = N'待审批') AS pending_appointment_count,
            (SELECT COUNT(*) FROM dbo.t_appeal WHERE status = N'待处理') AS pending_appeal_count,
            (SELECT COUNT(*) FROM dbo.t_blacklist WHERE is_active = 1) AS active_blacklist_count,
            (SELECT COUNT(*) FROM dbo.t_ai_query_log) AS ai_query_count;
        """
        stats = execute_query(sql)[0]
        latest_violations = execute_query("""
        SELECT TOP 6 v.violation_id, veh.plate_number, r.violation_type, r.violation_level,
               r.points_deducted, v.violation_time, v.location, v.status
        FROM dbo.t_violation AS v
        JOIN dbo.t_vehicle AS veh ON veh.vehicle_id = v.vehicle_id
        JOIN dbo.t_violation_rule AS r ON r.rule_code = v.rule_code
        ORDER BY v.violation_time DESC;
        """)
        active_penalties = execute_query("""
        SELECT TOP 6 p.penalty_id, p.penalty_type, p.trigger_type, p.status,
               COALESCE(tv.plate_number, sv.plate_number) AS plate_number, p.start_date, p.end_date
        FROM dbo.t_penalty AS p
        LEFT JOIN dbo.t_vehicle AS tv ON tv.vehicle_id = p.target_vehicle_id
        LEFT JOIN dbo.t_vehicle AS sv ON sv.vehicle_id = p.source_vehicle_id
        WHERE p.status IN (N'待执行', N'执行中')
        ORDER BY p.created_at DESC;
        """)
    else:
        registrant_id = user["registrant_id"]
        stats = execute_query(
            """
            SELECT
                (SELECT COUNT(*) FROM dbo.t_vehicle WHERE registrant_id = ?) AS vehicle_count,
                (SELECT COUNT(*) FROM dbo.t_vehicle WHERE registrant_id = ? AND register_status = N'正常') AS normal_vehicle_count,
                (SELECT COUNT(*) FROM dbo.t_violation WHERE status <> N'已撤销' AND vehicle_id IN (SELECT vehicle_id FROM dbo.t_vehicle WHERE registrant_id = ?)) AS violation_count,
                (SELECT COUNT(*) FROM dbo.t_penalty WHERE status IN (N'待执行', N'执行中') AND (
                    source_vehicle_id IN (SELECT vehicle_id FROM dbo.t_vehicle WHERE registrant_id = ?)
                    OR target_vehicle_id IN (SELECT vehicle_id FROM dbo.t_vehicle WHERE registrant_id = ?)
                    OR target_person_id = ?
                )) AS active_penalty_count,
                (SELECT COUNT(*) FROM dbo.t_appointment WHERE status = N'待审批' AND (
                    vehicle_id IN (SELECT vehicle_id FROM dbo.t_vehicle WHERE registrant_id = ?)
                    OR appointer_person_id = ?
                )) AS pending_appointment_count,
                (SELECT COUNT(*) FROM dbo.t_appeal WHERE status = N'待处理' AND applicant_id = ?) AS pending_appeal_count,
                CAST(0 AS INT) AS active_blacklist_count,
                CAST(0 AS INT) AS ai_query_count;
            """,
            [registrant_id, registrant_id, registrant_id, registrant_id, registrant_id, registrant_id, registrant_id, registrant_id, registrant_id],
        )[0]
        latest_violations = execute_query(
            """
            SELECT TOP 6 v.violation_id, veh.plate_number, r.violation_type, r.violation_level,
                   r.points_deducted, v.violation_time, v.location, v.status
            FROM dbo.t_violation AS v
            JOIN dbo.t_vehicle AS veh ON veh.vehicle_id = v.vehicle_id
            JOIN dbo.t_violation_rule AS r ON r.rule_code = v.rule_code
            WHERE veh.registrant_id = ?
            ORDER BY v.violation_time DESC;
            """,
            [registrant_id],
        )
        active_penalties = execute_query(
            """
            SELECT TOP 6 p.penalty_id, p.penalty_type, p.trigger_type, p.status,
                   COALESCE(tv.plate_number, sv.plate_number) AS plate_number, p.start_date, p.end_date
            FROM dbo.t_penalty AS p
            LEFT JOIN dbo.t_vehicle AS tv ON tv.vehicle_id = p.target_vehicle_id
            LEFT JOIN dbo.t_vehicle AS sv ON sv.vehicle_id = p.source_vehicle_id
            WHERE p.status IN (N'待执行', N'执行中') AND (
                p.source_vehicle_id IN (SELECT vehicle_id FROM dbo.t_vehicle WHERE registrant_id = ?)
                OR p.target_vehicle_id IN (SELECT vehicle_id FROM dbo.t_vehicle WHERE registrant_id = ?)
                OR p.target_person_id = ?
            )
            ORDER BY p.created_at DESC;
            """,
            [registrant_id, registrant_id, registrant_id],
        )
    return ok({"stats": stats, "latest_violations": latest_violations, "active_penalties": active_penalties})


@app.get("/api/options")
def options():
    user, error = require_user()
    if error:
        return error
    if is_admin(user):
        vehicles_sql = "SELECT vehicle_id AS id, plate_number + N' / ' + vehicle_type AS label FROM dbo.t_vehicle ORDER BY vehicle_id DESC;"
        appointments_sql = "SELECT appointment_id AS id, plate_number + N' / ' + status AS label FROM dbo.t_appointment ORDER BY appointment_id DESC;"
        periods_sql = "SELECT period_id AS id, CONVERT(NVARCHAR(20), vehicle_id) + N' / ' + CONVERT(NVARCHAR(4), [year]) AS label FROM dbo.t_scoring_period ORDER BY period_id DESC;"
        scoped_params: list[Any] = []
    else:
        vehicles_sql = "SELECT vehicle_id AS id, plate_number + N' / ' + vehicle_type AS label FROM dbo.t_vehicle WHERE registrant_id = ? ORDER BY vehicle_id DESC;"
        appointments_sql = """
            SELECT appointment_id AS id, plate_number + N' / ' + status AS label
            FROM dbo.t_appointment
            WHERE vehicle_id IN (SELECT vehicle_id FROM dbo.t_vehicle WHERE registrant_id = ?) OR appointer_person_id = ?
            ORDER BY appointment_id DESC;
        """
        periods_sql = "SELECT period_id AS id, CONVERT(NVARCHAR(20), vehicle_id) + N' / ' + CONVERT(NVARCHAR(4), [year]) AS label FROM dbo.t_scoring_period WHERE vehicle_id IN (SELECT vehicle_id FROM dbo.t_vehicle WHERE registrant_id = ?) ORDER BY period_id DESC;"
        scoped_params = [user["registrant_id"]]
    data = {
        "departments": execute_query("SELECT department_id AS id, dept_name AS label FROM dbo.t_department ORDER BY dept_name;") if is_admin(user) else [],
        "houses": execute_query("SELECT house_id AS id, house_code + N' - ' + owner_name AS label FROM dbo.t_house ORDER BY house_code;") if is_admin(user) else [],
        "registrants": execute_query("SELECT registrant_id AS id, name + N' / ' + phone AS label FROM dbo.t_registrant ORDER BY registrant_id DESC;") if is_admin(user) else execute_query("SELECT registrant_id AS id, name + N' / ' + phone AS label FROM dbo.t_registrant WHERE registrant_id = ?;", [user["registrant_id"]]),
        "users": execute_query("SELECT user_id AS id, real_name + N' / ' + role AS label FROM dbo.t_user ORDER BY user_id;") if is_admin(user) else execute_query("SELECT user_id AS id, real_name + N' / ' + role AS label FROM dbo.t_user WHERE user_id = ?;", [user["user_id"]]),
        "vehicles": execute_query(vehicles_sql, scoped_params),
        "rules": execute_query("SELECT rule_code AS id, rule_code + N' / ' + violation_level AS label FROM dbo.t_violation_rule ORDER BY rule_code;"),
        "appointments": execute_query(appointments_sql, scoped_params if is_admin(user) else [user["registrant_id"], user["registrant_id"]]),
        "periods": execute_query(periods_sql, scoped_params),
    }
    return ok(data)


@app.get("/api/<resource_name>")
def list_resource(resource_name: str):
    user, error = require_user()
    if error:
        return error
    resource = get_resource(resource_name)
    allowed, (scope_where, scope_params) = resource_access(resource_name, user)
    if not allowed:
        return fail("当前用户无权访问该资源", 403)
    limit = min(max(int(request.args.get("limit", 50)), 1), 200)
    offset = max(int(request.args.get("offset", 0)), 0)
    search = request.args.get("search")
    where, params = build_where(resource, search)
    where = combine_where([where, scope_where])
    params = [*params, *scope_params]
    columns = ", ".join(f"[{column}]" for column in resource.columns)
    count_sql = f"SELECT COUNT(*) AS total FROM dbo.{resource.table} {where};"
    data_sql = f"""
        SELECT {columns}
        FROM dbo.{resource.table}
        {where}
        ORDER BY {resource.default_order}
        OFFSET ? ROWS FETCH NEXT ? ROWS ONLY;
    """
    total = execute_query(count_sql, params)[0]["total"]
    rows = execute_query(data_sql, [*params, offset, limit])
    return ok({"items": rows, "total": total, "limit": limit, "offset": offset})


@app.get("/api/<resource_name>/<record_id>")
def get_one_resource(resource_name: str, record_id: str):
    user, error = require_user()
    if error:
        return error
    resource = get_resource(resource_name)
    allowed, (scope_where, scope_params) = resource_access(resource_name, user)
    if not allowed:
        return fail("当前用户无权访问该资源", 403)
    columns = ", ".join(f"[{column}]" for column in resource.columns)
    where = combine_where([f"[{resource.pk}] = ?", scope_where])
    rows = execute_query(f"SELECT {columns} FROM dbo.{resource.table} {where};", [record_id, *scope_params])
    if not rows:
        return fail("记录不存在", 404)
    return ok(rows[0])


@app.post("/api/<resource_name>")
def create_resource(resource_name: str):
    user, error = require_admin()
    if error:
        return error
    resource = get_resource(resource_name)
    payload = request.get_json(force=True) or {}
    columns, values = clean_payload(payload, resource.writable)
    if not columns:
        return fail("没有可写入的字段")
    record_id = insert_and_return_id(resource.table, columns, values, resource.pk)
    return ok({"id": record_id}, f"{resource.title}已新增", 201)


@app.put("/api/<resource_name>/<record_id>")
def update_resource(resource_name: str, record_id: str):
    user, error = require_admin()
    if error:
        return error
    resource = get_resource(resource_name)
    payload = request.get_json(force=True) or {}
    columns, values = clean_payload(payload, resource.writable)
    if not columns:
        return fail("没有可更新的字段")
    set_clause = ", ".join(f"[{column}] = ?" for column in columns)
    rowcount = execute_non_query(
        f"UPDATE dbo.{resource.table} SET {set_clause} WHERE [{resource.pk}] = ?;",
        [*values, record_id],
    )
    if rowcount == 0:
        return fail("记录不存在", 404)
    return ok({"affected": rowcount}, f"{resource.title}已更新")


@app.delete("/api/<resource_name>/<record_id>")
def delete_resource(resource_name: str, record_id: str):
    user, error = require_admin()
    if error:
        return error
    resource = get_resource(resource_name)
    rowcount = execute_non_query(f"DELETE FROM dbo.{resource.table} WHERE [{resource.pk}] = ?;", [record_id])
    if rowcount == 0:
        return fail("记录不存在", 404)
    return ok({"affected": rowcount}, f"{resource.title}已删除")


@app.post("/api/appointments/<int:appointment_id>/review")
def review_appointment(appointment_id: int):
    user, error = require_admin()
    if error:
        return error
    payload = request.get_json(force=True) or {}
    status = payload.get("status", "已通过")
    approver_id = payload.get("approver_id")
    if status not in {"已通过", "已驳回", "已取消"}:
        return fail("预约状态只能是已通过、已驳回或已取消")
    rowcount = execute_non_query(
        """
        UPDATE dbo.t_appointment
        SET status = ?, approver_id = ?, approved_at = CASE WHEN ? = N'已通过' THEN SYSDATETIME() ELSE approved_at END
        WHERE appointment_id = ?;
        """,
        [status, approver_id, status, appointment_id],
    )
    if rowcount == 0:
        return fail("预约记录不存在", 404)
    return ok({"affected": rowcount}, "预约审批已保存")


@app.post("/api/appeals/<int:appeal_id>/handle")
def handle_appeal(appeal_id: int):
    user, error = require_admin()
    if error:
        return error
    payload = request.get_json(force=True) or {}
    status = payload.get("status")
    handler_id = payload.get("handler_id")
    opinion = payload.get("handler_opinion")
    if status not in {"已通过", "已驳回", "已撤回"}:
        return fail("申诉处理状态只能是已通过、已驳回或已撤回")
    rowcount = execute_non_query(
        """
        UPDATE dbo.t_appeal
        SET status = ?, handler_id = ?, handler_opinion = ?, handled_at = SYSDATETIME()
        WHERE appeal_id = ?;
        """,
        [status, handler_id, opinion, appeal_id],
    )
    if rowcount == 0:
        return fail("申诉记录不存在", 404)
    return ok({"affected": rowcount}, "申诉处理结果已保存")


@app.get("/api/gate-check")
def gate_check():
    user, error = require_admin()
    if error:
        return error
    plate_number = request.args.get("plate", "").strip()
    if not plate_number:
        return fail("请提供车牌号参数 plate")

    rows = execute_query(
        """
        SELECT TOP 1 vehicle_id, plate_number, vehicle_type, register_status, status_end_date
        FROM dbo.t_vehicle
        WHERE plate_number = ?;
        """,
        [plate_number],
    )
    if not rows:
        return ok({"can_enter": False, "reason": "未找到车辆档案", "vehicle": None})

    vehicle = rows[0]
    blacklist = execute_query(
        """
        SELECT TOP 1 blacklist_id, blacklist_type, reason, start_date, end_date, is_active
        FROM dbo.t_blacklist
        WHERE vehicle_id = ? AND is_active = 1
        ORDER BY blacklist_id DESC;
        """,
        [vehicle["vehicle_id"]],
    )
    appointment = execute_query(
        """
        SELECT TOP 1 appointment_id, purpose, start_time, end_time, status
        FROM dbo.t_appointment
        WHERE vehicle_id = ? AND status = N'已通过' AND SYSDATETIME() BETWEEN start_time AND end_time
        ORDER BY start_time DESC;
        """,
        [vehicle["vehicle_id"]],
    )

    reason = "允许入校"
    can_enter = True
    if vehicle["register_status"] == "永久禁止":
        can_enter, reason = False, "车辆已永久禁止入校"
    elif vehicle["register_status"] == "暂停":
        can_enter, reason = False, "车辆处于暂停入校状态"
    elif blacklist:
        can_enter, reason = False, "车辆在有效黑名单中"
    elif vehicle["vehicle_type"] == "B" and not appointment:
        can_enter, reason = False, "B 类车辆当前无有效预约"

    return ok({"can_enter": can_enter, "reason": reason, "vehicle": vehicle, "blacklist": blacklist, "appointment": appointment})


@app.post("/api/ai-query/execute-readonly")
def execute_ai_readonly():
    user, error = require_admin()
    if error:
        return error
    payload = request.get_json(force=True) or {}
    requester_user_id = payload.get("requester_user_id")
    question = payload.get("natural_language_question", "")
    sql = (payload.get("generated_sql") or "").strip()

    if not requester_user_id or not question or not sql:
        return fail("请提供 requester_user_id、natural_language_question 和 generated_sql")
    if not sql.lower().startswith("select"):
        return fail("智能查询演示接口只允许 SELECT 语句")
    blocked = {" insert ", " update ", " delete ", " drop ", " alter ", " truncate ", " merge ", " exec "}
    lowered = f" {sql.lower()} "
    if any(token in lowered for token in blocked):
        return fail("SQL 包含非只读关键字，已拒绝执行")

    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql)
            rows = rows_to_dicts(cursor)
        log_id = insert_and_return_id(
            "t_ai_query_log",
            ["requester_user_id", "natural_language_question", "generated_sql", "is_readonly", "execution_status", "rows_returned", "executed_at"],
            [requester_user_id, question, sql, 1, "已执行", len(rows), None],
            "query_id",
        )
        execute_non_query("UPDATE dbo.t_ai_query_log SET executed_at = SYSDATETIME() WHERE query_id = ?;", [log_id])
        return ok({"rows": rows, "query_id": log_id}, "智能查询执行完成")
    except Exception as error:
        insert_and_return_id(
            "t_ai_query_log",
            ["requester_user_id", "natural_language_question", "generated_sql", "is_readonly", "execution_status", "error_message"],
            [requester_user_id, question, sql, 1, "执行失败", str(error)],
            "query_id",
        )
        raise


if __name__ == "__main__":
    app.run(host=config.host, port=config.port, debug=config.debug, use_reloader=False)
