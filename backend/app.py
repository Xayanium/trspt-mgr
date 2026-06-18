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


DATETIME_FIELDS = {"start_time", "end_time", "violation_time", "sent_time", "approved_at", "reviewed_at", "handled_at", "approved_at"}


def normalize_datetime_payload(payload: dict[str, Any]) -> None:
    for field in DATETIME_FIELDS:
        value = payload.get(field)
        if isinstance(value, str) and "T" in value:
            normalized = value.replace("T", " ")
            if len(normalized) == 16:
                normalized = f"{normalized}:00"
            payload[field] = normalized


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


def query_one(sql: str, params: list[Any] | None = None) -> dict[str, Any] | None:
    rows = execute_query(sql, params or [])
    return rows[0] if rows else None


def owner_username_for_registrant(payload: dict[str, Any]) -> str:
    return str(payload.get("account_username") or payload.get("phone") or "").strip()


def create_owner_user_for_registrant(payload: dict[str, Any], registrant_id: Any) -> str:
    username = owner_username_for_registrant(payload)
    if not username:
        raise ValueError("请提供登记人手机号或登录账号")
    if query_one("SELECT user_id FROM dbo.t_user WHERE username = ?;", [username]):
        raise ValueError("登录账号已存在，请更换账号")
    insert_and_return_id(
        "t_user",
        ["username", "password_hash", "real_name", "role", "phone", "department_id", "registrant_id"],
        [
            username,
            "FAKE_HASH_FOR_DEMO_ONLY",
            payload.get("name"),
            "车主",
            payload.get("phone"),
            payload.get("department_id"),
            registrant_id,
        ],
        "user_id",
    )
    return username


def expire_outdated_appointments() -> None:
    execute_non_query(
        """
        UPDATE dbo.t_appointment
        SET status = N'已过期'
        WHERE status IN (N'待审批', N'已通过')
          AND end_time < SYSDATETIME();
        """
    )


def list_appointments(user: dict[str, Any], search: str | None, offset: int, limit: int):
    expire_outdated_appointments()
    filters: list[str] = []
    params: list[Any] = []
    if search:
        filters.append("""
            (
                CONVERT(NVARCHAR(MAX), a.plate_number) LIKE ?
                OR CONVERT(NVARCHAR(MAX), a.appointer_type) LIKE ?
                OR CONVERT(NVARCHAR(MAX), d.dept_name) LIKE ?
                OR CONVERT(NVARCHAR(MAX), r.name) LIKE ?
                OR CONVERT(NVARCHAR(MAX), h.address) LIKE ?
                OR CONVERT(NVARCHAR(MAX), a.purpose) LIKE ?
                OR CONVERT(NVARCHAR(MAX), a.status) LIKE ?
            )
        """)
        params.extend([f"%{search}%"] * 7)
    if not is_admin(user):
        registrant_id = user["registrant_id"]
        filters.append("""
            (
                a.vehicle_id IN (SELECT vehicle_id FROM dbo.t_vehicle WHERE registrant_id = ?)
                OR a.appointer_person_id = ?
            )
        """)
        params.extend([registrant_id, registrant_id])

    where = combine_where(filters)
    appointer_display = """
        CASE
            WHEN a.appointer_type = N'房屋'
                THEN CONCAT(ISNULL(h.address, N'未指定房屋'), N'房屋业主')
            WHEN a.appointer_type = N'个人'
                THEN ISNULL(r.name, N'未指定个人')
            WHEN a.appointer_type = N'单位'
                THEN ISNULL(d.dept_name, N'未指定单位')
            ELSE a.appointer_type
        END
    """
    from_sql = f"""
        FROM dbo.t_appointment AS a
        LEFT JOIN dbo.t_department AS d ON d.department_id = a.appointer_dept_id
        LEFT JOIN dbo.t_registrant AS r ON r.registrant_id = a.appointer_person_id
        LEFT JOIN dbo.t_house AS h ON h.house_id = a.appointer_house_id
        {where}
    """
    count_sql = f"SELECT COUNT(*) AS total {from_sql};"
    data_sql = f"""
        SELECT
            a.appointment_id,
            a.vehicle_id,
            a.plate_number,
            a.appointer_type,
            a.appointer_dept_id,
            d.dept_name AS appointer_dept_name,
            a.appointer_person_id,
            r.name AS appointer_person_name,
            a.appointer_house_id,
            h.address AS appointer_house_address,
            {appointer_display} AS appointer_display,
            a.purpose,
            a.start_time,
            a.end_time,
            a.status,
            a.approver_id,
            a.approved_at,
            a.created_at
        {from_sql}
        ORDER BY a.appointment_id DESC
        OFFSET ? ROWS FETCH NEXT ? ROWS ONLY;
    """
    total = execute_query(count_sql, params)[0]["total"]
    rows = execute_query(data_sql, [*params, offset, limit])
    return ok({"items": rows, "total": total, "limit": limit, "offset": offset})


def list_vehicles(user: dict[str, Any], search: str | None, offset: int, limit: int):
    filters: list[str] = []
    params: list[Any] = []
    if search:
        filters.append("""
            (
                CONVERT(NVARCHAR(MAX), v.plate_number) LIKE ?
                OR CONVERT(NVARCHAR(MAX), v.vehicle_type) LIKE ?
                OR CONVERT(NVARCHAR(MAX), r.name) LIKE ?
                OR CONVERT(NVARCHAR(MAX), v.register_status) LIKE ?
                OR CONVERT(NVARCHAR(MAX), v.remark) LIKE ?
            )
        """)
        params.extend([f"%{search}%"] * 5)
    if not is_admin(user):
        filters.append("v.registrant_id = ?")
        params.append(user["registrant_id"])

    where = combine_where(filters)
    count_sql = f"""
        SELECT COUNT(*) AS total
        FROM dbo.t_vehicle AS v
        LEFT JOIN dbo.t_registrant AS r ON r.registrant_id = v.registrant_id
        {where};
    """
    data_sql = f"""
        SELECT
            v.vehicle_id,
            v.plate_number,
            v.vehicle_type,
            v.registrant_id,
            r.name AS registrant_name,
            v.register_status,
            v.register_date,
            v.status_start_date,
            v.status_end_date,
            v.remark,
            v.created_at,
            v.updated_at
        FROM dbo.t_vehicle AS v
        LEFT JOIN dbo.t_registrant AS r ON r.registrant_id = v.registrant_id
        {where}
        ORDER BY v.vehicle_id DESC
        OFFSET ? ROWS FETCH NEXT ? ROWS ONLY;
    """
    total = execute_query(count_sql, params)[0]["total"]
    rows = execute_query(data_sql, [*params, offset, limit])
    return ok({"items": rows, "total": total, "limit": limit, "offset": offset})


def list_violations(user: dict[str, Any], search: str | None, offset: int, limit: int):
    filters: list[str] = []
    params: list[Any] = []
    if search:
        filters.append("""
            (
                CONVERT(NVARCHAR(MAX), v.rule_code) LIKE ?
                OR CONVERT(NVARCHAR(MAX), veh.plate_number) LIKE ?
                OR CONVERT(NVARCHAR(MAX), r.violation_type) LIKE ?
                OR CONVERT(NVARCHAR(MAX), r.violation_level) LIKE ?
                OR CONVERT(NVARCHAR(MAX), v.location) LIKE ?
                OR CONVERT(NVARCHAR(MAX), v.source) LIKE ?
                OR CONVERT(NVARCHAR(MAX), v.status) LIKE ?
                OR CONVERT(NVARCHAR(MAX), v.remark) LIKE ?
            )
        """)
        params.extend([f"%{search}%"] * 8)
    if not is_admin(user):
        filters.append("veh.registrant_id = ?")
        params.append(user["registrant_id"])

    where = combine_where(filters)
    count_sql = f"""
        SELECT COUNT(*) AS total
        FROM dbo.t_violation AS v
        JOIN dbo.t_vehicle AS veh ON veh.vehicle_id = v.vehicle_id
        JOIN dbo.t_violation_rule AS r ON r.rule_code = v.rule_code
        {where};
    """
    data_sql = f"""
        SELECT
            v.violation_id,
            v.vehicle_id,
            veh.plate_number,
            v.appointment_id,
            v.rule_code,
            r.violation_type,
            r.violation_level,
            v.violation_time,
            v.location,
            v.speed,
            v.speed_limit,
            v.evidence_path,
            v.source,
            v.status,
            v.remark,
            v.created_at
        FROM dbo.t_violation AS v
        JOIN dbo.t_vehicle AS veh ON veh.vehicle_id = v.vehicle_id
        JOIN dbo.t_violation_rule AS r ON r.rule_code = v.rule_code
        {where}
        ORDER BY v.violation_id DESC
        OFFSET ? ROWS FETCH NEXT ? ROWS ONLY;
    """
    total = execute_query(count_sql, params)[0]["total"]
    rows = execute_query(data_sql, [*params, offset, limit])
    return ok({"items": rows, "total": total, "limit": limit, "offset": offset})


def list_penalties(user: dict[str, Any], search: str | None, offset: int, limit: int):
    filters: list[str] = []
    params: list[Any] = []
    if search:
        filters.append("""
            (
                CONVERT(NVARCHAR(MAX), sv.plate_number) LIKE ?
                OR CONVERT(NVARCHAR(MAX), p.trigger_type) LIKE ?
                OR CONVERT(NVARCHAR(MAX), p.penalty_type) LIKE ?
                OR CONVERT(NVARCHAR(MAX), p.status) LIKE ?
                OR CONVERT(NVARCHAR(MAX), d.dept_name) LIKE ?
                OR CONVERT(NVARCHAR(MAX), h.address) LIKE ?
            )
        """)
        params.extend([f"%{search}%"] * 6)
    if not is_admin(user):
        registrant_id = user["registrant_id"]
        filters.append("""
            (
                p.source_vehicle_id IN (SELECT vehicle_id FROM dbo.t_vehicle WHERE registrant_id = ?)
                OR p.target_vehicle_id IN (SELECT vehicle_id FROM dbo.t_vehicle WHERE registrant_id = ?)
                OR p.target_person_id = ?
            )
        """)
        params.extend([registrant_id, registrant_id, registrant_id])

    where = combine_where(filters)
    penalty_description = """
        CASE
            WHEN p.penalty_type = N'扣分'
                THEN CONCAT(N'扣', p.points_deducted, N'分')
            WHEN p.penalty_type = N'暂停入校'
                THEN CONCAT(N'扣', p.points_deducted, N'分并暂停入校', ISNULL(CONVERT(NVARCHAR(20), p.suspension_days), N'0'), N'天')
            WHEN p.penalty_type = N'预约黑名单'
                THEN CONCAT(N'扣', p.points_deducted, N'分并预约黑名单')
            WHEN p.penalty_type = N'通报单位'
                THEN CONCAT(N'通报单位[', ISNULL(d.dept_name, N'未指定单位'), N']')
            WHEN p.penalty_type = N'取消房屋预约'
                THEN CONCAT(N'取消房屋预约：', ISNULL(h.address, N'未指定房屋'), N' ', ISNULL(CONVERT(NVARCHAR(20), p.suspension_days), N'0'), N' 天')
            ELSE p.penalty_type
        END
    """
    from_sql = f"""
        FROM dbo.t_penalty AS p
        LEFT JOIN dbo.t_vehicle AS sv ON sv.vehicle_id = p.source_vehicle_id
        LEFT JOIN dbo.t_department AS d ON d.department_id = p.target_dept_id
        LEFT JOIN dbo.t_house AS h ON h.house_id = p.target_house_id
        {where}
    """
    count_sql = f"SELECT COUNT(*) AS total {from_sql};"
    data_sql = f"""
        SELECT
            p.penalty_id,
            p.violation_id,
            p.source_vehicle_id,
            sv.plate_number AS source_plate_number,
            p.period_id,
            p.trigger_type,
            p.penalty_type,
            {penalty_description} AS penalty_description,
            p.points_deducted,
            p.suspension_days,
            p.start_date,
            p.end_date,
            p.target_vehicle_id,
            p.target_dept_id,
            d.dept_name AS target_dept_name,
            p.target_person_id,
            p.target_house_id,
            h.address AS target_house_address,
            p.status,
            p.created_at
        {from_sql}
        ORDER BY p.penalty_id DESC
        OFFSET ? ROWS FETCH NEXT ? ROWS ONLY;
    """
    total = execute_query(count_sql, params)[0]["total"]
    rows = execute_query(data_sql, [*params, offset, limit])
    return ok({"items": rows, "total": total, "limit": limit, "offset": offset})


def list_appeals(user: dict[str, Any], search: str | None, offset: int, limit: int):
    filters: list[str] = []
    params: list[Any] = []
    if search:
        filters.append("""
            (
                CONVERT(NVARCHAR(MAX), v.remark) LIKE ?
                OR CONVERT(NVARCHAR(MAX), r.name) LIKE ?
                OR CONVERT(NVARCHAR(MAX), a.reason) LIKE ?
                OR CONVERT(NVARCHAR(MAX), a.status) LIKE ?
                OR CONVERT(NVARCHAR(MAX), a.handler_opinion) LIKE ?
            )
        """)
        params.extend([f"%{search}%"] * 5)
    if not is_admin(user):
        filters.append("a.applicant_id = ?")
        params.append(user["registrant_id"])

    where = combine_where(filters)
    from_sql = f"""
        FROM dbo.t_appeal AS a
        LEFT JOIN dbo.t_violation AS v ON v.violation_id = a.violation_id
        LEFT JOIN dbo.t_registrant AS r ON r.registrant_id = a.applicant_id
        {where}
    """
    count_sql = f"SELECT COUNT(*) AS total {from_sql};"
    data_sql = f"""
        SELECT
            a.appeal_id,
            a.violation_id,
            v.remark AS violation_remark,
            a.applicant_id,
            r.name AS applicant_name,
            a.reason,
            a.evidence_path,
            a.status,
            a.handler_id,
            a.handler_opinion,
            a.applied_at,
            a.handled_at
        {from_sql}
        ORDER BY a.appeal_id DESC
        OFFSET ? ROWS FETCH NEXT ? ROWS ONLY;
    """
    total = execute_query(count_sql, params)[0]["total"]
    rows = execute_query(data_sql, [*params, offset, limit])
    return ok({"items": rows, "total": total, "limit": limit, "offset": offset})


def list_points_additions(user: dict[str, Any], search: str | None, offset: int, limit: int):
    filters: list[str] = []
    params: list[Any] = []
    if search:
        filters.append("""
            (
                CONVERT(NVARCHAR(MAX), v.plate_number) LIKE ?
                OR CONVERT(NVARCHAR(MAX), r.name) LIKE ?
                OR CONVERT(NVARCHAR(MAX), a.status) LIKE ?
                OR CONVERT(NVARCHAR(MAX), a.approver_opinion) LIKE ?
            )
        """)
        params.extend([f"%{search}%"] * 4)
    if not is_admin(user):
        registrant_id = user["registrant_id"]
        filters.append("""
            (
                a.applicant_id = ?
                OR a.vehicle_id IN (SELECT vehicle_id FROM dbo.t_vehicle WHERE registrant_id = ?)
            )
        """)
        params.extend([registrant_id, registrant_id])

    where = combine_where(filters)
    from_sql = f"""
        FROM dbo.t_points_addition_log AS a
        LEFT JOIN dbo.t_vehicle AS v ON v.vehicle_id = a.vehicle_id
        LEFT JOIN dbo.t_registrant AS r ON r.registrant_id = a.applicant_id
        {where}
    """
    count_sql = f"SELECT COUNT(*) AS total {from_sql};"
    data_sql = f"""
        SELECT
            a.addition_id,
            a.period_id,
            a.vehicle_id,
            v.plate_number,
            a.applicant_id,
            r.name AS applicant_name,
            a.addition_points,
            a.proof_path,
            a.status,
            a.approver_id,
            a.approver_opinion,
            a.applied_at,
            a.approved_at
        {from_sql}
        ORDER BY a.addition_id DESC
        OFFSET ? ROWS FETCH NEXT ? ROWS ONLY;
    """
    total = execute_query(count_sql, params)[0]["total"]
    rows = execute_query(data_sql, [*params, offset, limit])
    return ok({"items": rows, "total": total, "limit": limit, "offset": offset})


def list_scoring_periods(user: dict[str, Any], search: str | None, offset: int, limit: int):
    filters: list[str] = []
    params: list[Any] = []
    if search:
        filters.append("""
            (
                CONVERT(NVARCHAR(MAX), v.plate_number) LIKE ?
                OR CONVERT(NVARCHAR(MAX), p.year) LIKE ?
                OR CONVERT(NVARCHAR(MAX), p.has_danger_violation) LIKE ?
                OR CONVERT(NVARCHAR(MAX), p.is_active) LIKE ?
            )
        """)
        params.extend([f"%{search}%"] * 4)
    if not is_admin(user):
        filters.append("v.registrant_id = ?")
        params.append(user["registrant_id"])

    where = combine_where(filters)
    from_sql = f"""
        FROM dbo.t_scoring_period AS p
        LEFT JOIN dbo.t_vehicle AS v ON v.vehicle_id = p.vehicle_id
        {where}
    """
    count_sql = f"SELECT COUNT(*) AS total {from_sql};"
    data_sql = f"""
        SELECT
            p.period_id,
            p.vehicle_id,
            v.plate_number,
            p.year,
            p.initial_points,
            p.deducted_points_total,
            p.added_points_total,
            p.add_count,
            p.remaining_points,
            p.has_danger_violation,
            p.is_active,
            p.created_at
        {from_sql}
        ORDER BY p.period_id DESC
        OFFSET ? ROWS FETCH NEXT ? ROWS ONLY;
    """
    total = execute_query(count_sql, params)[0]["total"]
    rows = execute_query(data_sql, [*params, offset, limit])
    return ok({"items": rows, "total": total, "limit": limit, "offset": offset})


def list_blacklists(user: dict[str, Any], search: str | None, offset: int, limit: int):
    filters: list[str] = []
    params: list[Any] = []
    if search:
        filters.append("""
            (
                CONVERT(NVARCHAR(MAX), v.plate_number) LIKE ?
                OR CONVERT(NVARCHAR(MAX), b.blacklist_type) LIKE ?
                OR CONVERT(NVARCHAR(MAX), b.reason) LIKE ?
                OR CONVERT(NVARCHAR(MAX), b.penalty_id) LIKE ?
                OR CONVERT(NVARCHAR(MAX), b.is_active) LIKE ?
            )
        """)
        params.extend([f"%{search}%"] * 5)
    if not is_admin(user):
        filters.append("v.registrant_id = ?")
        params.append(user["registrant_id"])

    where = combine_where(filters)
    from_sql = f"""
        FROM dbo.t_blacklist AS b
        LEFT JOIN dbo.t_vehicle AS v ON v.vehicle_id = b.vehicle_id
        {where}
    """
    count_sql = f"SELECT COUNT(*) AS total {from_sql};"
    data_sql = f"""
        SELECT
            b.blacklist_id,
            b.vehicle_id,
            v.plate_number,
            b.blacklist_type,
            b.reason,
            b.source_type,
            b.penalty_id,
            b.start_date,
            b.end_date,
            b.is_active,
            b.created_at
        {from_sql}
        ORDER BY b.blacklist_id DESC
        OFFSET ? ROWS FETCH NEXT ? ROWS ONLY;
    """
    total = execute_query(count_sql, params)[0]["total"]
    rows = execute_query(data_sql, [*params, offset, limit])
    return ok({"items": rows, "total": total, "limit": limit, "offset": offset})


def today_sql() -> str:
    return "CONVERT(date, SYSDATETIME())"


def create_penalty(
    *,
    violation_id: Any | None,
    source_vehicle_id: Any | None,
    period_id: Any | None,
    trigger_type: str,
    penalty_type: str,
    points_deducted: int = 0,
    suspension_days: int | None = None,
    start_date_sql: str = "CONVERT(date, SYSDATETIME())",
    end_date_sql: str | None = None,
    target_vehicle_id: Any | None = None,
    target_dept_id: Any | None = None,
    target_person_id: Any | None = None,
    target_house_id: Any | None = None,
    status: str = "执行中",
) -> Any:
    sql = f"""
        INSERT INTO dbo.t_penalty
            (violation_id, source_vehicle_id, period_id, trigger_type, penalty_type, points_deducted,
             suspension_days, start_date, end_date, target_vehicle_id, target_dept_id, target_person_id,
             target_house_id, status)
        OUTPUT INSERTED.penalty_id
        VALUES (?, ?, ?, ?, ?, ?, ?, {start_date_sql}, {end_date_sql or 'NULL'}, ?, ?, ?, ?, ?);
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            sql,
            [
                violation_id,
                source_vehicle_id,
                period_id,
                trigger_type,
                penalty_type,
                points_deducted,
                suspension_days,
                target_vehicle_id,
                target_dept_id,
                target_person_id,
                target_house_id,
                status,
            ],
        )
        return cursor.fetchone()[0]


def add_or_refresh_blacklist(vehicle_id: Any, penalty_id: Any | None, blacklist_type: str, reason: str, days: int | None = None) -> None:
    existing = query_one(
        "SELECT blacklist_id FROM dbo.t_blacklist WHERE vehicle_id = ? AND is_active = 1;",
        [vehicle_id],
    )
    if existing:
        execute_non_query(
            """
            UPDATE dbo.t_blacklist
            SET blacklist_type = ?, reason = ?, penalty_id = COALESCE(?, penalty_id),
                end_date = CASE WHEN ? IS NULL THEN NULL ELSE DATEADD(day, ?, CONVERT(date, SYSDATETIME())) END
            WHERE blacklist_id = ?;
            """,
            [blacklist_type, reason, penalty_id, days, days, existing["blacklist_id"]],
        )
        return
    execute_non_query(
        """
        INSERT INTO dbo.t_blacklist
            (vehicle_id, blacklist_type, reason, source_type, penalty_id, start_date, end_date, is_active)
        VALUES (?, ?, ?, N'处罚触发', ?, CONVERT(date, SYSDATETIME()),
                CASE WHEN ? IS NULL THEN NULL ELSE DATEADD(day, ?, CONVERT(date, SYSDATETIME())) END, 1);
        """,
        [vehicle_id, blacklist_type, reason, penalty_id, days, days],
    )


def ensure_scoring_period(vehicle_id: Any, year: int) -> dict[str, Any]:
    period = query_one(
        "SELECT * FROM dbo.t_scoring_period WHERE vehicle_id = ? AND [year] = ?;",
        [vehicle_id, year],
    )
    if period:
        return period
    period_id = insert_and_return_id(
        "t_scoring_period",
        ["vehicle_id", "year", "initial_points", "deducted_points_total", "added_points_total", "add_count", "has_danger_violation", "is_active"],
        [vehicle_id, year, 12, 0, 0, 0, 0, 1],
        "period_id",
    )
    return query_one("SELECT * FROM dbo.t_scoring_period WHERE period_id = ?;", [period_id]) or {"period_id": period_id, "deducted_points_total": 0}


def apply_vehicle_suspension(vehicle_id: Any, days: int, reason: str, violation_id: Any, period_id: Any, points: int, trigger_type: str = "累计扣分") -> Any:
    penalty_id = create_penalty(
        violation_id=violation_id,
        source_vehicle_id=vehicle_id,
        period_id=period_id,
        trigger_type=trigger_type,
        penalty_type="暂停入校",
        points_deducted=points,
        suspension_days=days,
        end_date_sql=f"DATEADD(day, {days}, CONVERT(date, SYSDATETIME()))",
        target_vehicle_id=vehicle_id,
    )
    execute_non_query(
        """
        UPDATE dbo.t_vehicle
        SET register_status = N'暂停',
            status_start_date = CONVERT(date, SYSDATETIME()),
            status_end_date = DATEADD(day, ?, CONVERT(date, SYSDATETIME()))
        WHERE vehicle_id = ? AND register_status <> N'永久禁止';
        """,
        [days, vehicle_id],
    )
    return penalty_id


def apply_vehicle_thresholds(vehicle: dict[str, Any], period: dict[str, Any], previous_total: int, current_total: int, violation_id: Any, points: int) -> None:
    vehicle_id = vehicle["vehicle_id"]
    vehicle_type = vehicle["vehicle_type"]
    if vehicle_type == "B":
        if previous_total < 6 <= current_total:
            penalty_id = create_penalty(
                violation_id=violation_id,
                source_vehicle_id=vehicle_id,
                period_id=period["period_id"],
                trigger_type="累计扣分",
                penalty_type="预约黑名单",
                points_deducted=0,
                target_vehicle_id=vehicle_id,
            )
            add_or_refresh_blacklist(vehicle_id, penalty_id, "永久", "B 类车辆单车累计扣分达到 6 分，列入预约黑名单")
        return

    if vehicle_type == "C" and previous_total < 12 <= current_total:
        apply_vehicle_suspension(vehicle_id, 365, "C 类车辆累计扣分达到 12 分", violation_id, period["period_id"], points)
        return

    if vehicle_type != "A":
        return

    thresholds = [(12, 15), (24, 30), (36, 365)]
    for threshold, days in thresholds:
        if previous_total < threshold <= current_total:
            apply_vehicle_suspension(
                vehicle_id,
                days,
                f"A 类车辆累计扣分达到 {threshold} 分",
                violation_id,
                period["period_id"],
                0,
            )
            if threshold == 24 and vehicle.get("registrant_id"):
                create_penalty(
                    violation_id=violation_id,
                    source_vehicle_id=vehicle_id,
                    period_id=period["period_id"],
                    trigger_type="累计扣分",
                    penalty_type="谈话提醒",
                    target_person_id=vehicle["registrant_id"],
                    status="待执行",
                )


def upsert_b_summary_and_penalty(violation: dict[str, Any], points: int) -> None:
    if points <= 0 or not violation.get("appointment_id"):
        return
    appointment = query_one(
        """
        SELECT appointment_id, appointer_type, appointer_dept_id, appointer_person_id, appointer_house_id
        FROM dbo.t_appointment
        WHERE appointment_id = ?;
        """,
        [violation["appointment_id"]],
    )
    if not appointment:
        return
    appointer_type = appointment["appointer_type"]
    year = int(str(violation["violation_time"])[:4])
    target_field = {
        "单位": "appointer_dept_id",
        "个人": "appointer_person_id",
        "房屋": "appointer_house_id",
    }[appointer_type]
    target_id = appointment[target_field]
    if not target_id:
        return

    existing = query_one(
        f"""
        SELECT summary_id, accumulated_points
        FROM dbo.t_b_appointer_violation_summary
        WHERE appointer_type = ? AND {target_field} = ? AND [year] = ?;
        """,
        [appointer_type, target_id, year],
    )
    previous_total = int(existing["accumulated_points"]) if existing else 0
    current_total = previous_total + points
    if existing:
        execute_non_query(
            """
            UPDATE dbo.t_b_appointer_violation_summary
            SET accumulated_points = ?, last_violation_time = ?, penalty_triggered = CASE WHEN ? = 1 THEN 1 ELSE penalty_triggered END
            WHERE summary_id = ?;
            """,
            [current_total, violation["violation_time"], 0, existing["summary_id"]],
        )
    else:
        values = {
            "appointer_type": appointer_type,
            "appointer_dept_id": appointment["appointer_dept_id"],
            "appointer_person_id": appointment["appointer_person_id"],
            "appointer_house_id": appointment["appointer_house_id"],
            "year": year,
            "accumulated_points": current_total,
            "last_violation_time": violation["violation_time"],
            "penalty_triggered": 0,
        }
        insert_and_return_id(
            "t_b_appointer_violation_summary",
            list(values.keys()),
            list(values.values()),
            "summary_id",
        )

    if appointer_type == "单位" and previous_total < 24 <= current_total:
        create_penalty(
            violation_id=violation["violation_id"],
            source_vehicle_id=violation["vehicle_id"],
            period_id=violation["period_id"],
            trigger_type="累计扣分",
            penalty_type="通报单位",
            target_dept_id=target_id,
            status="已完成",
        )
    elif appointer_type == "个人" and previous_total < 24 <= current_total:
        create_penalty(
            violation_id=violation["violation_id"],
            source_vehicle_id=violation["vehicle_id"],
            period_id=violation["period_id"],
            trigger_type="累计扣分",
            penalty_type="暂停因私预约",
            suspension_days=15,
            end_date_sql="DATEADD(day, 15, CONVERT(date, SYSDATETIME()))",
            target_person_id=target_id,
        )
        execute_non_query(
            """
            UPDATE dbo.t_registrant
            SET appointment_status = N'暂停', appointment_suspend_until = DATEADD(day, 15, CONVERT(date, SYSDATETIME()))
            WHERE registrant_id = ?;
            """,
            [target_id],
        )
    elif appointer_type == "房屋" and previous_total < 12 <= current_total:
        create_penalty(
            violation_id=violation["violation_id"],
            source_vehicle_id=violation["vehicle_id"],
            period_id=violation["period_id"],
            trigger_type="累计扣分",
            penalty_type="取消房屋预约",
            suspension_days=30,
            end_date_sql="DATEADD(day, 30, CONVERT(date, SYSDATETIME()))",
            target_house_id=target_id,
        )
        execute_non_query(
            """
            UPDATE dbo.t_house
            SET appointment_status = N'暂停', appointment_suspend_until = DATEADD(day, 30, CONVERT(date, SYSDATETIME()))
            WHERE house_id = ?;
            """,
            [target_id],
        )


def process_confirmed_violation(violation_id: Any) -> None:
    violation = query_one(
        """
        SELECT v.violation_id, v.vehicle_id, v.appointment_id, v.rule_code, v.violation_time, v.status,
               r.points_deducted, r.violation_level, r.is_malicious,
               veh.vehicle_type, veh.registrant_id
        FROM dbo.t_violation AS v
        JOIN dbo.t_violation_rule AS r ON r.rule_code = v.rule_code
        JOIN dbo.t_vehicle AS veh ON veh.vehicle_id = v.vehicle_id
        WHERE v.violation_id = ?;
        """,
        [violation_id],
    )
    if not violation or violation["status"] != "已确认":
        return

    vehicle = {
        "vehicle_id": violation["vehicle_id"],
        "vehicle_type": violation["vehicle_type"],
        "registrant_id": violation["registrant_id"],
    }
    year = int(str(violation["violation_time"])[:4])
    period = ensure_scoring_period(violation["vehicle_id"], year)
    violation["period_id"] = period["period_id"]

    if violation["is_malicious"]:
        penalty_id = create_penalty(
            violation_id=violation_id,
            source_vehicle_id=violation["vehicle_id"],
            period_id=period["period_id"],
            trigger_type="恶性行为",
            penalty_type="永久禁止",
            target_vehicle_id=violation["vehicle_id"],
        )
        execute_non_query(
            """
            UPDATE dbo.t_vehicle
            SET register_status = N'永久禁止', status_start_date = CONVERT(date, SYSDATETIME()), status_end_date = NULL
            WHERE vehicle_id = ?;
            """,
            [violation["vehicle_id"]],
        )
        add_or_refresh_blacklist(violation["vehicle_id"], penalty_id, "永久", "恶性交通行为，永久禁止入校")
        return

    points = int(violation["points_deducted"] or 0)
    previous_total = int(period.get("deducted_points_total") or 0)
    current_total = previous_total + points
    is_danger = points >= 12 or "危险" in str(violation["violation_level"])
    execute_non_query(
        """
        UPDATE dbo.t_scoring_period
        SET deducted_points_total = ?, has_danger_violation = CASE WHEN ? = 1 THEN 1 ELSE has_danger_violation END
        WHERE period_id = ?;
        """,
        [current_total, 1 if is_danger else 0, period["period_id"]],
    )

    if points > 0:
        create_penalty(
            violation_id=violation_id,
            source_vehicle_id=violation["vehicle_id"],
            period_id=period["period_id"],
            trigger_type="单次违规",
            penalty_type="扣分",
            points_deducted=points,
            target_vehicle_id=violation["vehicle_id"],
            status="已完成",
        )

    if is_danger and points >= 12:
        apply_vehicle_suspension(
            violation["vehicle_id"],
            60,
            "危险违规一次性扣 12 分",
            violation_id,
            period["period_id"],
            points,
            "单次违规",
        )
        create_penalty(
            violation_id=violation_id,
            source_vehicle_id=violation["vehicle_id"],
            period_id=period["period_id"],
            trigger_type="单次违规",
            penalty_type="全校通报",
            target_vehicle_id=violation["vehicle_id"],
            status="已完成",
        )
    else:
        apply_vehicle_thresholds(vehicle, {"period_id": period["period_id"]}, previous_total, current_total, violation_id, points)

    if violation["vehicle_type"] == "B":
        upsert_b_summary_and_penalty(violation, points)


def restriction_reason_for_appointment(appointment_id: Any) -> str | None:
    appointment = query_one(
        """
        SELECT a.*, v.vehicle_type, v.register_status, v.status_end_date
        FROM dbo.t_appointment AS a
        JOIN dbo.t_vehicle AS v ON v.vehicle_id = a.vehicle_id
        WHERE a.appointment_id = ?;
        """,
        [appointment_id],
    )
    if not appointment:
        return "预约记录不存在"
    if appointment["register_status"] == "永久禁止":
        return "车辆已永久禁止入校"
    if appointment["register_status"] == "暂停":
        active = query_one(
            "SELECT CASE WHEN ? IS NULL OR ? >= CONVERT(date, SYSDATETIME()) THEN 1 ELSE 0 END AS active;",
            [appointment["status_end_date"], appointment["status_end_date"]],
        )
        if active and active["active"] == 1:
            return "车辆仍处于暂停入校期"
    if query_one("SELECT blacklist_id FROM dbo.t_blacklist WHERE vehicle_id = ? AND is_active = 1;", [appointment["vehicle_id"]]):
        return "车辆在有效黑名单中"
    if appointment["appointer_type"] == "个人" and appointment["appointer_person_id"]:
        person = query_one(
            "SELECT appointment_status, appointment_suspend_until FROM dbo.t_registrant WHERE registrant_id = ?;",
            [appointment["appointer_person_id"]],
        )
        if person and person["appointment_status"] != "正常" and (person["appointment_suspend_until"] is None or str(person["appointment_suspend_until"]) >= str(query_one(f"SELECT {today_sql()} AS today;")["today"])):
            return "预约人预约权限处于暂停/取消状态"
    if appointment["appointer_type"] == "房屋" and appointment["appointer_house_id"]:
        house = query_one(
            "SELECT appointment_status, appointment_suspend_until FROM dbo.t_house WHERE house_id = ?;",
            [appointment["appointer_house_id"]],
        )
        if house and house["appointment_status"] != "正常" and (house["appointment_suspend_until"] is None or str(house["appointment_suspend_until"]) >= str(query_one(f"SELECT {today_sql()} AS today;")["today"])):
            return "房屋预约权限处于暂停/取消状态"
    return None


def apply_points_addition_review(addition_id: Any, status: str, opinion: str | None, approver_id: Any) -> tuple[dict[str, Any] | None, str | None]:
    if status not in {"待审批", "已通过", "已驳回", "已撤回"}:
        return None, "学习申请状态只能是待审批、已通过、已驳回或已撤回"
    addition = query_one(
        """
        SELECT a.*, p.deducted_points_total, p.add_count, v.vehicle_type, v.register_status, v.status_end_date
        FROM dbo.t_points_addition_log AS a
        JOIN dbo.t_scoring_period AS p ON p.period_id = a.period_id
        JOIN dbo.t_vehicle AS v ON v.vehicle_id = a.vehicle_id
        WHERE a.addition_id = ?;
        """,
        [addition_id],
    )
    if not addition:
        return None, "学习申请不存在"

    old_status = addition["status"]
    if old_status != "待审批" and status != old_status:
        return None, "该学习申请已经处理，不能变更审批状态"

    if status == "已通过" and old_status != "已通过":
        if addition["vehicle_type"] != "A":
            return None, "仅 A 类车辆可通过学习恢复权限"
        if int(addition["deducted_points_total"]) not in (12, 24):
            return None, "只有累计扣分为 12 或 24 分时才能通过学习申请"
        if int(addition["add_count"]) >= 2:
            return None, "本年度学习恢复次数已达上限"
        execute_non_query(
            """
            UPDATE dbo.t_scoring_period
            SET added_points_total = added_points_total + ?, add_count = add_count + 1
            WHERE period_id = ?;
            """,
            [addition["addition_points"], addition["period_id"]],
        )
        if addition["register_status"] == "暂停":
            execute_non_query(
                """
                UPDATE dbo.t_vehicle
                SET register_status = N'正常', status_start_date = NULL, status_end_date = NULL
                WHERE vehicle_id = ? AND register_status = N'暂停';
                """,
                [addition["vehicle_id"]],
            )

    execute_non_query(
        """
        UPDATE dbo.t_points_addition_log
        SET status = ?,
            approver_id = ?,
            approver_opinion = ?,
            approved_at = CASE WHEN ? IN (N'已通过', N'已驳回') THEN SYSDATETIME() ELSE approved_at END
        WHERE addition_id = ?;
        """,
        [status, approver_id, opinion, status, addition_id],
    )
    return {"id": addition_id}, None


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
        vehicles_sql = "SELECT vehicle_id AS id, plate_number + N' / ' + vehicle_type + N' / ' + register_status AS label FROM dbo.t_vehicle ORDER BY vehicle_id DESC;"
        appointments_sql = "SELECT appointment_id AS id, plate_number + N' / ' + status AS label FROM dbo.t_appointment ORDER BY appointment_id DESC;"
        periods_sql = "SELECT period_id AS id, CONVERT(NVARCHAR(20), vehicle_id) + N' / ' + CONVERT(NVARCHAR(4), [year]) AS label FROM dbo.t_scoring_period ORDER BY period_id DESC;"
        scoped_params: list[Any] = []
    else:
        vehicles_sql = "SELECT vehicle_id AS id, plate_number + N' / ' + vehicle_type + N' / ' + register_status AS label FROM dbo.t_vehicle WHERE registrant_id = ? ORDER BY vehicle_id DESC;"
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
    if resource_name == "appointments":
        return list_appointments(user, search, offset, limit)
    if resource_name == "vehicles":
        return list_vehicles(user, search, offset, limit)
    if resource_name == "violations":
        return list_violations(user, search, offset, limit)
    if resource_name == "penalties":
        return list_penalties(user, search, offset, limit)
    if resource_name == "appeals":
        return list_appeals(user, search, offset, limit)
    if resource_name == "points-additions":
        return list_points_additions(user, search, offset, limit)
    if resource_name == "scoring-periods":
        return list_scoring_periods(user, search, offset, limit)
    if resource_name == "blacklists":
        return list_blacklists(user, search, offset, limit)
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
    user, error = require_user()
    if error:
        return error
    owner_creatable = {"vehicles", "appointments", "appeals", "points-additions"}
    if not is_admin(user) and not (is_owner(user) and resource_name in owner_creatable):
        return fail("当前用户无权新增该资源", 403)
    resource = get_resource(resource_name)
    payload = request.get_json(force=True) or {}
    normalize_datetime_payload(payload)

    if is_admin(user) and resource_name == "appointments":
        return fail("预约入校应由车主自行提交，管理员仅支持查询和修改预约记录", 403)
    if is_admin(user) and resource_name == "points-additions":
        return fail("加分申请应由车主自行提交，管理员仅支持审批和管理申请记录", 403)
    if is_admin(user) and resource_name == "registrants":
        account_username = owner_username_for_registrant(payload)
        if not account_username:
            return fail("新增登记人时需要提供手机号或登录账号")
        if query_one("SELECT user_id FROM dbo.t_user WHERE username = ?;", [account_username]):
            return fail("登录账号已存在，请更换账号")

    if is_owner(user):
        registrant_id = user["registrant_id"]
        if resource_name == "vehicles":
            payload["registrant_id"] = registrant_id
            payload["register_status"] = "待审批"
            payload["status_start_date"] = None
            payload["status_end_date"] = None
        elif resource_name == "appointments":
            vehicle = query_one("SELECT vehicle_id, plate_number, vehicle_type, register_status FROM dbo.t_vehicle WHERE vehicle_id = ? AND registrant_id = ?;", [payload.get("vehicle_id"), registrant_id])
            if not vehicle:
                return fail("只能为本人车辆提交预约")
            if vehicle["vehicle_type"] != "B":
                return fail("只有 B 类车辆需要提交预约入校")
            if vehicle["register_status"] != "正常":
                return fail("只有状态正常的 B 类车辆可以提交预约入校")
            payload["plate_number"] = vehicle["plate_number"]
            payload["appointer_type"] = "个人"
            payload["appointer_person_id"] = registrant_id
            payload["appointer_dept_id"] = None
            payload["appointer_house_id"] = None
            payload["status"] = "待审批"
            payload["approver_id"] = None
            payload["approved_at"] = None
        elif resource_name == "appeals":
            violation = query_one(
                """
                SELECT v.violation_id
                FROM dbo.t_violation AS v
                JOIN dbo.t_vehicle AS veh ON veh.vehicle_id = v.vehicle_id
                WHERE v.violation_id = ? AND veh.registrant_id = ?;
                """,
                [payload.get("violation_id"), registrant_id],
            )
            if not violation:
                return fail("只能对本人车辆违规提交申诉")
            payload["applicant_id"] = registrant_id
            payload["status"] = "待处理"
            payload["handler_id"] = None
            payload["handler_opinion"] = None
            payload["handled_at"] = None
        elif resource_name == "points-additions":
            vehicle = query_one("SELECT vehicle_id, vehicle_type FROM dbo.t_vehicle WHERE vehicle_id = ? AND registrant_id = ?;", [payload.get("vehicle_id"), registrant_id])
            if not vehicle:
                return fail("只能为本人车辆提交学习申请")
            if vehicle["vehicle_type"] != "A":
                return fail("当前规则仅允许 A 类注册车辆提交学习申请")
            period = query_one(
                """
                SELECT TOP 1 period_id, deducted_points_total, add_count
                FROM dbo.t_scoring_period
                WHERE vehicle_id = ? AND is_active = 1
                ORDER BY [year] DESC;
                """,
                [payload.get("vehicle_id")],
            )
            if not period:
                return fail("车辆没有活跃记分周期，无法提交学习申请")
            if int(period["deducted_points_total"]) not in (12, 24):
                return fail("只有累计扣分达到 12 或 24 分时才能提交学习申请")
            if int(period["add_count"]) >= 2:
                return fail("本年度学习恢复次数已达上限")
            payload["period_id"] = period["period_id"]
            payload["applicant_id"] = registrant_id
            payload["addition_points"] = payload.get("addition_points") or 12
            payload["status"] = "待审批"
            payload["approver_id"] = None
            payload["approver_opinion"] = None
            payload["approved_at"] = None

    columns, values = clean_payload(payload, resource.writable)
    if not columns:
        return fail("没有可写入的字段")
    record_id = insert_and_return_id(resource.table, columns, values, resource.pk)
    account_username = None
    if resource_name == "registrants":
        try:
            account_username = create_owner_user_for_registrant(payload, record_id)
        except ValueError as error:
            return fail(str(error))
    if resource_name == "violations":
        process_confirmed_violation(record_id)
    data = {"id": record_id}
    if account_username:
        data["username"] = account_username
        data["default_password"] = "123456"
    return ok(data, f"{resource.title}已新增", 201)


@app.put("/api/<resource_name>/<record_id>")
def update_resource(resource_name: str, record_id: str):
    user, error = require_admin()
    if error:
        return error
    resource = get_resource(resource_name)
    payload = request.get_json(force=True) or {}
    normalize_datetime_payload(payload)
    if resource_name == "points-additions":
        allowed = {"status", "approver_id", "approver_opinion"}
        payload = {key: value for key, value in payload.items() if key in allowed}
        status = payload.get("status")
        if not status:
            return fail("请提供审批状态")
        approver_id = payload.get("approver_id") or user["user_id"]
        result, error_message = apply_points_addition_review(record_id, status, payload.get("approver_opinion"), approver_id)
        if error_message:
            status_code = 404 if error_message == "学习申请不存在" else 400
            return fail(error_message, status_code)
        return ok(result, "学习申请审批结果已保存")
    if resource_name == "appointments":
        status = payload.get("status")
        if status not in {"待审批", "已通过", "已驳回", "已取消", "已过期"}:
            return fail("预约状态只能是待审批、已通过、已驳回、已取消或已过期")
        if status == "已通过":
            reason = restriction_reason_for_appointment(record_id)
            if reason:
                return fail(f"预约审批被拦截：{reason}")
        rowcount = execute_non_query(
            """
            UPDATE dbo.t_appointment
            SET status = ?,
                approver_id = ?,
                approved_at = CASE WHEN ? = N'已通过' THEN SYSDATETIME() ELSE approved_at END
            WHERE appointment_id = ?;
            """,
            [status, user["user_id"], status, record_id],
        )
        if rowcount == 0:
            return fail("记录不存在", 404)
        return ok({"affected": rowcount}, "预约状态已更新")
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
    user, error = require_user()
    if error:
        return error
    if not is_admin(user):
        if not (is_owner(user) and resource_name == "points-additions"):
            return fail("当前用户无权删除该资源", 403)
        existing = query_one(
            "SELECT addition_id, status FROM dbo.t_points_addition_log WHERE addition_id = ? AND applicant_id = ?;",
            [record_id, user["registrant_id"]],
        )
        if not existing:
            return fail("记录不存在", 404)
        if existing["status"] == "已通过":
            return fail("已通过的加分申请不能由车主删除", 400)
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
    if status not in {"已通过", "已驳回", "已取消"}:
        return fail("预约状态只能是已通过、已驳回或已取消")
    if status == "已通过":
        reason = restriction_reason_for_appointment(appointment_id)
        if reason:
            return fail(f"预约审批被拦截：{reason}")
    rowcount = execute_non_query(
        """
        UPDATE dbo.t_appointment
        SET status = ?, approver_id = ?, approved_at = CASE WHEN ? = N'已通过' THEN SYSDATETIME() ELSE approved_at END
        WHERE appointment_id = ?;
        """,
        [status, user["user_id"], status, appointment_id],
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


@app.post("/api/points-additions/<int:addition_id>/review")
def review_points_addition(addition_id: int):
    user, error = require_admin()
    if error:
        return error
    payload = request.get_json(force=True) or {}
    status = payload.get("status")
    opinion = payload.get("approver_opinion")
    if status not in {"已通过", "已驳回"}:
        return fail("学习申请审批状态只能是已通过或已驳回")
    result, error_message = apply_points_addition_review(addition_id, status, opinion, user["user_id"])
    if error_message:
        status_code = 404 if error_message == "学习申请不存在" else 400
        return fail(error_message, status_code)
    return ok(result, "学习申请审批结果已保存")


@app.post("/api/scoring-periods/annual-reset")
def annual_reset():
    user, error = require_admin()
    if error:
        return error
    payload = request.get_json(force=True) or {}
    year = int(payload.get("year") or query_one("SELECT YEAR(SYSDATETIME()) AS [year];")["year"])
    if year < 2020 or year > 2099:
        return fail("年度必须在 2020 到 2099 之间")
    execute_non_query("UPDATE dbo.t_scoring_period SET is_active = 0 WHERE [year] <> ?;", [year])
    vehicle_ids = execute_query("SELECT vehicle_id FROM dbo.t_vehicle WHERE register_status <> N'注销';")
    created = 0
    for vehicle in vehicle_ids:
        existing = query_one("SELECT period_id FROM dbo.t_scoring_period WHERE vehicle_id = ? AND [year] = ?;", [vehicle["vehicle_id"], year])
        if not existing:
            insert_and_return_id(
                "t_scoring_period",
                ["vehicle_id", "year", "initial_points", "deducted_points_total", "added_points_total", "add_count", "has_danger_violation", "is_active"],
                [vehicle["vehicle_id"], year, 12, 0, 0, 0, 0, 1],
                "period_id",
            )
            created += 1
        else:
            execute_non_query("UPDATE dbo.t_scoring_period SET is_active = 1 WHERE period_id = ?;", [existing["period_id"]])
    execute_non_query(
        """
        UPDATE dbo.t_vehicle
        SET register_status = N'正常', status_start_date = NULL, status_end_date = NULL
        WHERE register_status = N'暂停' AND status_end_date IS NOT NULL AND status_end_date < CONVERT(date, SYSDATETIME());
        """
    )
    execute_non_query(
        """
        UPDATE dbo.t_blacklist
        SET is_active = 0
        WHERE is_active = 1 AND end_date IS NOT NULL AND end_date < CONVERT(date, SYSDATETIME());
        """
    )
    execute_non_query(
        """
        UPDATE dbo.t_registrant
        SET appointment_status = N'正常', appointment_suspend_until = NULL
        WHERE appointment_status = N'暂停' AND appointment_suspend_until IS NOT NULL AND appointment_suspend_until < CONVERT(date, SYSDATETIME());
        """
    )
    execute_non_query(
        """
        UPDATE dbo.t_house
        SET appointment_status = N'正常', appointment_suspend_until = NULL
        WHERE appointment_status = N'暂停' AND appointment_suspend_until IS NOT NULL AND appointment_suspend_until < CONVERT(date, SYSDATETIME());
        """
    )
    return ok({"year": year, "created_periods": created}, "年度重置完成")


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
    if vehicle["register_status"] == "暂停" and vehicle["status_end_date"]:
        expired = query_one(
            "SELECT CASE WHEN ? < CONVERT(date, SYSDATETIME()) THEN 1 ELSE 0 END AS expired;",
            [vehicle["status_end_date"]],
        )
        if expired and expired["expired"] == 1:
            execute_non_query(
                """
                UPDATE dbo.t_vehicle
                SET register_status = N'正常', status_start_date = NULL, status_end_date = NULL
                WHERE vehicle_id = ? AND register_status = N'暂停';
                """,
                [vehicle["vehicle_id"]],
            )
            vehicle["register_status"] = "正常"
            vehicle["status_end_date"] = None
    execute_non_query(
        """
        UPDATE dbo.t_blacklist
        SET is_active = 0
        WHERE vehicle_id = ? AND is_active = 1 AND end_date IS NOT NULL AND end_date < CONVERT(date, SYSDATETIME());
        """,
        [vehicle["vehicle_id"]],
    )
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
