from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Resource:
    table: str
    pk: str
    title: str
    columns: tuple[str, ...]
    writable: tuple[str, ...]
    searchable: tuple[str, ...]
    default_order: str


RESOURCES: dict[str, Resource] = {
    "departments": Resource(
        "t_department",
        "department_id",
        "单位",
        ("department_id", "dept_name", "dept_type", "contact_name", "contact_phone"),
        ("dept_name", "dept_type", "contact_name", "contact_phone"),
        ("dept_name", "dept_type", "contact_name"),
        "department_id DESC",
    ),
    "houses": Resource(
        "t_house",
        "house_id",
        "房屋",
        ("house_id", "house_code", "address", "owner_name", "owner_phone", "appointment_status", "appointment_suspend_until"),
        ("house_code", "address", "owner_name", "owner_phone", "appointment_status", "appointment_suspend_until"),
        ("house_code", "address", "owner_name", "owner_phone"),
        "house_id DESC",
    ),
    "registrants": Resource(
        "t_registrant",
        "registrant_id",
        "登记人",
        ("registrant_id", "name", "identity_type", "department_id", "house_id", "phone", "id_number", "appointment_status", "appointment_suspend_until", "created_at"),
        ("name", "identity_type", "department_id", "house_id", "phone", "id_number", "appointment_status", "appointment_suspend_until"),
        ("name", "identity_type", "phone", "id_number"),
        "registrant_id DESC",
    ),
    "vehicles": Resource(
        "t_vehicle",
        "vehicle_id",
        "车辆",
        ("vehicle_id", "plate_number", "vehicle_type", "registrant_id", "register_status", "register_date", "status_start_date", "status_end_date", "remark", "created_at", "updated_at"),
        ("plate_number", "vehicle_type", "registrant_id", "register_status", "register_date", "status_start_date", "status_end_date", "remark"),
        ("plate_number", "vehicle_type", "register_status", "remark"),
        "vehicle_id DESC",
    ),
    "registration-applications": Resource(
        "t_vehicle_registration_application",
        "application_id",
        "注册申请",
        ("application_id", "vehicle_id", "applicant_registrant_id", "plate_number", "vehicle_type", "apply_type", "apply_reason", "material_path", "apply_status", "reviewer_id", "review_opinion", "applied_at", "reviewed_at"),
        ("vehicle_id", "applicant_registrant_id", "plate_number", "vehicle_type", "apply_type", "apply_reason", "material_path", "apply_status", "reviewer_id", "review_opinion", "reviewed_at"),
        ("plate_number", "apply_type", "apply_status", "apply_reason"),
        "application_id DESC",
    ),
    "permits": Resource(
        "t_vehicle_permit",
        "permit_id",
        "通行权限",
        ("permit_id", "vehicle_id", "application_id", "permit_type", "valid_from", "valid_to", "permit_status", "issued_by", "issued_at"),
        ("vehicle_id", "application_id", "permit_type", "valid_from", "valid_to", "permit_status", "issued_by"),
        ("permit_type", "permit_status"),
        "permit_id DESC",
    ),
    "appointments": Resource(
        "t_appointment",
        "appointment_id",
        "预约",
        ("appointment_id", "vehicle_id", "plate_number", "appointer_type", "appointer_dept_id", "appointer_person_id", "appointer_house_id", "purpose", "start_time", "end_time", "status", "approver_id", "approved_at", "created_at"),
        ("vehicle_id", "plate_number", "appointer_type", "appointer_dept_id", "appointer_person_id", "appointer_house_id", "purpose", "start_time", "end_time", "status", "approver_id", "approved_at"),
        ("plate_number", "appointer_type", "purpose", "status"),
        "appointment_id DESC",
    ),
    "violation-rules": Resource(
        "t_violation_rule",
        "rule_code",
        "违规规则",
        ("rule_code", "violation_type", "violation_level", "points_deducted", "speed_min", "speed_max", "is_malicious", "is_active", "description"),
        ("rule_code", "violation_type", "violation_level", "points_deducted", "speed_min", "speed_max", "is_malicious", "is_active", "description"),
        ("rule_code", "violation_type", "violation_level", "description"),
        "rule_code ASC",
    ),
    "violations": Resource(
        "t_violation",
        "violation_id",
        "违规",
        ("violation_id", "vehicle_id", "appointment_id", "rule_code", "violation_time", "location", "speed", "speed_limit", "evidence_path", "source", "status", "remark", "created_at"),
        ("vehicle_id", "appointment_id", "rule_code", "violation_time", "location", "speed", "speed_limit", "evidence_path", "source", "status", "remark"),
        ("rule_code", "location", "source", "status", "remark"),
        "violation_id DESC",
    ),
    "scoring-periods": Resource(
        "t_scoring_period",
        "period_id",
        "记分周期",
        ("period_id", "vehicle_id", "year", "initial_points", "deducted_points_total", "added_points_total", "add_count", "remaining_points", "has_danger_violation", "is_active", "created_at"),
        ("vehicle_id", "year", "initial_points", "deducted_points_total", "added_points_total", "add_count", "has_danger_violation", "is_active"),
        ("year",),
        "period_id DESC",
    ),
    "points-additions": Resource(
        "t_points_addition_log",
        "addition_id",
        "加分申请",
        ("addition_id", "period_id", "vehicle_id", "applicant_id", "addition_points", "proof_path", "status", "approver_id", "approver_opinion", "applied_at", "approved_at"),
        ("period_id", "vehicle_id", "applicant_id", "addition_points", "proof_path", "status", "approver_id", "approver_opinion", "approved_at"),
        ("status", "approver_opinion"),
        "addition_id DESC",
    ),
    "penalties": Resource(
        "t_penalty",
        "penalty_id",
        "处罚",
        ("penalty_id", "violation_id", "source_vehicle_id", "period_id", "trigger_type", "penalty_type", "points_deducted", "suspension_days", "start_date", "end_date", "target_vehicle_id", "target_dept_id", "target_person_id", "target_house_id", "status", "created_at"),
        ("violation_id", "source_vehicle_id", "period_id", "trigger_type", "penalty_type", "points_deducted", "suspension_days", "start_date", "end_date", "target_vehicle_id", "target_dept_id", "target_person_id", "target_house_id", "status"),
        ("trigger_type", "penalty_type", "status"),
        "penalty_id DESC",
    ),
    "blacklists": Resource(
        "t_blacklist",
        "blacklist_id",
        "黑名单",
        ("blacklist_id", "vehicle_id", "blacklist_type", "reason", "source_type", "penalty_id", "start_date", "end_date", "is_active", "created_at"),
        ("vehicle_id", "blacklist_type", "reason", "source_type", "penalty_id", "start_date", "end_date", "is_active"),
        ("blacklist_type", "reason", "source_type"),
        "blacklist_id DESC",
    ),
    "b-summaries": Resource(
        "t_b_appointer_violation_summary",
        "summary_id",
        "B类汇总",
        ("summary_id", "appointer_type", "appointer_dept_id", "appointer_person_id", "appointer_house_id", "year", "accumulated_points", "last_violation_time", "penalty_triggered"),
        ("appointer_type", "appointer_dept_id", "appointer_person_id", "appointer_house_id", "year", "accumulated_points", "last_violation_time", "penalty_triggered"),
        ("appointer_type", "year"),
        "summary_id DESC",
    ),
    "appeals": Resource(
        "t_appeal",
        "appeal_id",
        "申诉",
        ("appeal_id", "violation_id", "applicant_id", "reason", "evidence_path", "status", "handler_id", "handler_opinion", "applied_at", "handled_at"),
        ("violation_id", "applicant_id", "reason", "evidence_path", "status", "handler_id", "handler_opinion", "handled_at"),
        ("reason", "status", "handler_opinion"),
        "appeal_id DESC",
    ),
    "notifications": Resource(
        "t_notification_log",
        "notification_id",
        "通知",
        ("notification_id", "vehicle_id", "violation_id", "penalty_id", "notification_type", "recipient", "recipient_type", "content", "sent_time", "send_status", "created_at"),
        ("vehicle_id", "violation_id", "penalty_id", "notification_type", "recipient", "recipient_type", "content", "sent_time", "send_status"),
        ("notification_type", "recipient", "recipient_type", "content", "send_status"),
        "notification_id DESC",
    ),
    "notification-recipients": Resource(
        "t_notification_recipient",
        "recipient_id",
        "通知接收人",
        ("recipient_id", "role_label", "department_id", "name", "phone", "is_active", "updated_at"),
        ("role_label", "department_id", "name", "phone", "is_active"),
        ("role_label", "name", "phone"),
        "recipient_id DESC",
    ),
    "ai-query-templates": Resource(
        "t_ai_query_template",
        "template_id",
        "智能查询模板",
        ("template_id", "template_name", "description", "safe_sql", "allowed_role", "is_active", "created_at"),
        ("template_name", "description", "safe_sql", "allowed_role", "is_active"),
        ("template_name", "description", "allowed_role"),
        "template_id DESC",
    ),
    "ai-query-logs": Resource(
        "t_ai_query_log",
        "query_id",
        "智能查询日志",
        ("query_id", "requester_user_id", "natural_language_question", "generated_sql", "is_readonly", "execution_status", "rows_returned", "error_message", "executed_at", "created_at"),
        ("requester_user_id", "natural_language_question", "generated_sql", "is_readonly", "execution_status", "rows_returned", "error_message", "executed_at"),
        ("natural_language_question", "execution_status", "error_message"),
        "query_id DESC",
    ),
}
