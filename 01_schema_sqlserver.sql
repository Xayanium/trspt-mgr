/*
  Campus smart traffic management database
  Target DBMS: Microsoft SQL Server

  Run this script before 02_seed_mock_data.sql.
  The schema keeps the report's main entities, with several practical fixes:
  - vehicle registration applications and permits are modeled explicitly;
  - scoring uses yearly accumulated deduction instead of duplicated current points;
  - one violation may create multiple penalties;
  - B-class appointment-party summaries are unified into one compact table;
  - optional AI query assistant audit tables are included at the end.
*/

USE SchoolDB;
GO

SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO
/*
  Campus smart traffic management database
  Target DBMS: Microsoft SQL Server

  Run this script before 02_seed_mock_data.sql.
  The schema keeps the report's main entities, with several practical fixes:
  - vehicle registration applications and permits are modeled explicitly;
  - scoring uses yearly accumulated deduction instead of duplicated current points;
  - one violation may create multiple penalties;
  - B-class appointment-party summaries are unified into one compact table;
  - optional AI query assistant audit tables are included at the end.
*/

SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

-- ========== 1. 先删除所有表（按依赖顺序，先删子表） ==========
IF OBJECT_ID(N'dbo.t_ai_query_log', N'U') IS NOT NULL DROP TABLE dbo.t_ai_query_log;
IF OBJECT_ID(N'dbo.t_ai_query_template', N'U') IS NOT NULL DROP TABLE dbo.t_ai_query_template;
IF OBJECT_ID(N'dbo.t_notification_recipient', N'U') IS NOT NULL DROP TABLE dbo.t_notification_recipient;
IF OBJECT_ID(N'dbo.t_notification_log', N'U') IS NOT NULL DROP TABLE dbo.t_notification_log;
IF OBJECT_ID(N'dbo.t_b_appointer_violation_summary', N'U') IS NOT NULL DROP TABLE dbo.t_b_appointer_violation_summary;
IF OBJECT_ID(N'dbo.t_blacklist', N'U') IS NOT NULL DROP TABLE dbo.t_blacklist;
IF OBJECT_ID(N'dbo.t_penalty', N'U') IS NOT NULL DROP TABLE dbo.t_penalty;
IF OBJECT_ID(N'dbo.t_points_addition_log', N'U') IS NOT NULL DROP TABLE dbo.t_points_addition_log;
IF OBJECT_ID(N'dbo.t_scoring_period', N'U') IS NOT NULL DROP TABLE dbo.t_scoring_period;
IF OBJECT_ID(N'dbo.t_appeal', N'U') IS NOT NULL DROP TABLE dbo.t_appeal;
IF OBJECT_ID(N'dbo.t_violation', N'U') IS NOT NULL DROP TABLE dbo.t_violation;
IF OBJECT_ID(N'dbo.t_appointment', N'U') IS NOT NULL DROP TABLE dbo.t_appointment;
IF OBJECT_ID(N'dbo.t_vehicle_permit', N'U') IS NOT NULL DROP TABLE dbo.t_vehicle_permit;
IF OBJECT_ID(N'dbo.t_vehicle_registration_application', N'U') IS NOT NULL DROP TABLE dbo.t_vehicle_registration_application;
IF OBJECT_ID(N'dbo.t_vehicle', N'U') IS NOT NULL DROP TABLE dbo.t_vehicle;
IF OBJECT_ID(N'dbo.t_user', N'U') IS NOT NULL DROP TABLE dbo.t_user;
IF OBJECT_ID(N'dbo.t_registrant', N'U') IS NOT NULL DROP TABLE dbo.t_registrant;
IF OBJECT_ID(N'dbo.t_house', N'U') IS NOT NULL DROP TABLE dbo.t_house;
IF OBJECT_ID(N'dbo.t_department', N'U') IS NOT NULL DROP TABLE dbo.t_department;
IF OBJECT_ID(N'dbo.t_violation_rule', N'U') IS NOT NULL DROP TABLE dbo.t_violation_rule;
GO

-- ========== 2. 创建表 ==========
CREATE TABLE dbo.t_department (
    department_id INT IDENTITY(1,1) NOT NULL CONSTRAINT pk_department PRIMARY KEY,
    dept_name NVARCHAR(100) NOT NULL CONSTRAINT uq_department_name UNIQUE,
    dept_type NVARCHAR(20) NOT NULL,
    contact_name NVARCHAR(50) NULL,
    contact_phone NVARCHAR(20) NULL,
    CONSTRAINT ck_department_type CHECK (dept_type IN (N'教学', N'行政', N'后勤', N'其他'))
);

CREATE TABLE dbo.t_house (
    house_id INT IDENTITY(1,1) NOT NULL CONSTRAINT pk_house PRIMARY KEY,
    house_code NVARCHAR(50) NOT NULL CONSTRAINT uq_house_code UNIQUE,
    address NVARCHAR(200) NOT NULL,
    owner_name NVARCHAR(50) NOT NULL,
    owner_phone NVARCHAR(20) NOT NULL,
    appointment_status NVARCHAR(10) NOT NULL CONSTRAINT df_house_appointment_status DEFAULT N'正常',
    appointment_suspend_until DATE NULL,
    CONSTRAINT ck_house_appointment_status CHECK (appointment_status IN (N'正常', N'暂停', N'取消'))
);

CREATE TABLE dbo.t_registrant (
    registrant_id INT IDENTITY(1,1) NOT NULL CONSTRAINT pk_registrant PRIMARY KEY,
    name NVARCHAR(50) NOT NULL,
    identity_type NVARCHAR(20) NOT NULL,
    department_id INT NULL,
    house_id INT NULL,
    phone NVARCHAR(20) NOT NULL,
    id_number NVARCHAR(30) NULL,
    appointment_status NVARCHAR(10) NOT NULL CONSTRAINT df_registrant_appointment_status DEFAULT N'正常',
    appointment_suspend_until DATE NULL,
    created_at DATETIME2(0) NOT NULL CONSTRAINT df_registrant_created_at DEFAULT SYSDATETIME(),
    CONSTRAINT fk_registrant_department FOREIGN KEY (department_id) REFERENCES dbo.t_department(department_id),
    CONSTRAINT fk_registrant_house FOREIGN KEY (house_id) REFERENCES dbo.t_house(house_id),
    CONSTRAINT ck_registrant_identity_type CHECK (identity_type IN (N'教职工', N'学生', N'购租户', N'外来人员', N'其他')),
    CONSTRAINT ck_registrant_appointment_status CHECK (appointment_status IN (N'正常', N'暂停', N'取消'))
);

CREATE TABLE dbo.t_user (
    user_id INT IDENTITY(1,1) NOT NULL CONSTRAINT pk_user PRIMARY KEY,
    username NVARCHAR(50) NOT NULL CONSTRAINT uq_user_username UNIQUE,
    password_hash NVARCHAR(255) NOT NULL,
    real_name NVARCHAR(50) NOT NULL,
    role NVARCHAR(20) NOT NULL,
    phone NVARCHAR(20) NULL,
    department_id INT NULL,
    registrant_id INT NULL,
    is_active BIT NOT NULL CONSTRAINT df_user_is_active DEFAULT 1,
    created_at DATETIME2(0) NOT NULL CONSTRAINT df_user_created_at DEFAULT SYSDATETIME(),
    CONSTRAINT fk_user_department FOREIGN KEY (department_id) REFERENCES dbo.t_department(department_id),
    CONSTRAINT fk_user_registrant FOREIGN KEY (registrant_id) REFERENCES dbo.t_registrant(registrant_id),
    CONSTRAINT ck_user_role CHECK (role IN (N'系统管理员', N'保卫处管理员', N'审核员', N'车主', N'单位联系人'))
);

CREATE TABLE dbo.t_vehicle (
    vehicle_id INT IDENTITY(1,1) NOT NULL CONSTRAINT pk_vehicle PRIMARY KEY,
    plate_number NVARCHAR(20) NOT NULL CONSTRAINT uq_vehicle_plate_number UNIQUE,
    vehicle_type CHAR(1) NOT NULL,
    registrant_id INT NULL,
    register_status NVARCHAR(10) NOT NULL CONSTRAINT df_vehicle_register_status DEFAULT N'正常',
    register_date DATETIME2(0) NOT NULL CONSTRAINT df_vehicle_register_date DEFAULT SYSDATETIME(),
    status_start_date DATE NULL,
    status_end_date DATE NULL,
    remark NVARCHAR(500) NULL,
    created_at DATETIME2(0) NOT NULL CONSTRAINT df_vehicle_created_at DEFAULT SYSDATETIME(),
    updated_at DATETIME2(0) NOT NULL CONSTRAINT df_vehicle_updated_at DEFAULT SYSDATETIME(),
    CONSTRAINT fk_vehicle_registrant FOREIGN KEY (registrant_id) REFERENCES dbo.t_registrant(registrant_id),
    CONSTRAINT ck_vehicle_type CHECK (vehicle_type IN ('A', 'B', 'C')),
    CONSTRAINT ck_vehicle_register_status CHECK (register_status IN (N'待审批', N'正常', N'暂停', N'永久禁止', N'注销')),
    CONSTRAINT ck_vehicle_status_date CHECK (
        status_end_date IS NULL OR status_start_date IS NULL OR status_end_date >= status_start_date
    )
);

CREATE TABLE dbo.t_violation_rule (
    rule_code NVARCHAR(20) NOT NULL CONSTRAINT pk_violation_rule PRIMARY KEY,
    violation_type NVARCHAR(20) NOT NULL,
    violation_level NVARCHAR(20) NOT NULL,
    points_deducted INT NOT NULL,
    speed_min SMALLINT NULL,
    speed_max SMALLINT NULL,
    is_malicious BIT NOT NULL CONSTRAINT df_violation_rule_is_malicious DEFAULT 0,
    is_active BIT NOT NULL CONSTRAINT df_violation_rule_is_active DEFAULT 1,
    description NVARCHAR(200) NULL,
    CONSTRAINT ck_violation_rule_points CHECK (points_deducted >= 0),
    CONSTRAINT ck_violation_rule_speed_range CHECK (
        speed_min IS NULL OR speed_max IS NULL OR speed_max >= speed_min
    )
);

CREATE TABLE dbo.t_vehicle_registration_application (
    application_id INT IDENTITY(1,1) NOT NULL CONSTRAINT pk_vehicle_registration_application PRIMARY KEY,
    vehicle_id INT NULL,
    applicant_registrant_id INT NOT NULL,
    plate_number NVARCHAR(20) NOT NULL,
    vehicle_type CHAR(1) NOT NULL,
    apply_type NVARCHAR(10) NOT NULL,
    apply_reason NVARCHAR(500) NULL,
    material_path NVARCHAR(500) NULL,
    apply_status NVARCHAR(10) NOT NULL CONSTRAINT df_vehicle_application_status DEFAULT N'待审批',
    reviewer_id INT NULL,
    review_opinion NVARCHAR(500) NULL,
    applied_at DATETIME2(0) NOT NULL CONSTRAINT df_vehicle_application_applied_at DEFAULT SYSDATETIME(),
    reviewed_at DATETIME2(0) NULL,
    CONSTRAINT fk_vehicle_application_vehicle FOREIGN KEY (vehicle_id) REFERENCES dbo.t_vehicle(vehicle_id),
    CONSTRAINT fk_vehicle_application_applicant FOREIGN KEY (applicant_registrant_id) REFERENCES dbo.t_registrant(registrant_id),
    CONSTRAINT fk_vehicle_application_reviewer FOREIGN KEY (reviewer_id) REFERENCES dbo.t_user(user_id),
    CONSTRAINT ck_vehicle_application_type CHECK (vehicle_type IN ('A', 'B', 'C')),
    CONSTRAINT ck_vehicle_application_apply_type CHECK (apply_type IN (N'注册', N'续期', N'变更', N'注销')),
    CONSTRAINT ck_vehicle_application_status CHECK (apply_status IN (N'待审批', N'已通过', N'已驳回', N'已撤回'))
);

CREATE TABLE dbo.t_vehicle_permit (
    permit_id INT IDENTITY(1,1) NOT NULL CONSTRAINT pk_vehicle_permit PRIMARY KEY,
    vehicle_id INT NOT NULL,
    application_id INT NULL,
    permit_type NVARCHAR(20) NOT NULL,
    valid_from DATE NOT NULL,
    valid_to DATE NOT NULL,
    permit_status NVARCHAR(10) NOT NULL CONSTRAINT df_vehicle_permit_status DEFAULT N'有效',
    issued_by INT NULL,
    issued_at DATETIME2(0) NOT NULL CONSTRAINT df_vehicle_permit_issued_at DEFAULT SYSDATETIME(),
    CONSTRAINT fk_vehicle_permit_vehicle FOREIGN KEY (vehicle_id) REFERENCES dbo.t_vehicle(vehicle_id),
    CONSTRAINT fk_vehicle_permit_application FOREIGN KEY (application_id) REFERENCES dbo.t_vehicle_registration_application(application_id),
    CONSTRAINT fk_vehicle_permit_issued_by FOREIGN KEY (issued_by) REFERENCES dbo.t_user(user_id),
    CONSTRAINT ck_vehicle_permit_type CHECK (permit_type IN (N'固定通行', N'临时预约', N'摩托车通行')),
    CONSTRAINT ck_vehicle_permit_status CHECK (permit_status IN (N'有效', N'暂停', N'过期', N'注销')),
    CONSTRAINT ck_vehicle_permit_date CHECK (valid_to >= valid_from)
);

CREATE TABLE dbo.t_appointment (
    appointment_id INT IDENTITY(1,1) NOT NULL CONSTRAINT pk_appointment PRIMARY KEY,
    vehicle_id INT NOT NULL,
    plate_number NVARCHAR(20) NOT NULL,
    appointer_type NVARCHAR(10) NOT NULL,
    appointer_dept_id INT NULL,
    appointer_person_id INT NULL,
    appointer_house_id INT NULL,
    purpose NVARCHAR(200) NOT NULL,
    start_time DATETIME2(0) NOT NULL,
    end_time DATETIME2(0) NOT NULL,
    status NVARCHAR(10) NOT NULL CONSTRAINT df_appointment_status DEFAULT N'待审批',
    approver_id INT NULL,
    approved_at DATETIME2(0) NULL,
    created_at DATETIME2(0) NOT NULL CONSTRAINT df_appointment_created_at DEFAULT SYSDATETIME(),
    CONSTRAINT fk_appointment_vehicle FOREIGN KEY (vehicle_id) REFERENCES dbo.t_vehicle(vehicle_id),
    CONSTRAINT fk_appointment_dept FOREIGN KEY (appointer_dept_id) REFERENCES dbo.t_department(department_id),
    CONSTRAINT fk_appointment_person FOREIGN KEY (appointer_person_id) REFERENCES dbo.t_registrant(registrant_id),
    CONSTRAINT fk_appointment_house FOREIGN KEY (appointer_house_id) REFERENCES dbo.t_house(house_id),
    CONSTRAINT fk_appointment_approver FOREIGN KEY (approver_id) REFERENCES dbo.t_user(user_id),
    CONSTRAINT ck_appointment_type CHECK (appointer_type IN (N'单位', N'个人', N'房屋')),
    CONSTRAINT ck_appointment_status CHECK (status IN (N'待审批', N'已通过', N'已驳回', N'已取消', N'已过期')),
    CONSTRAINT ck_appointment_time CHECK (end_time > start_time),
    CONSTRAINT ck_appointment_appointer CHECK (
        (appointer_type = N'单位' AND appointer_dept_id IS NOT NULL AND appointer_person_id IS NULL AND appointer_house_id IS NULL) OR
        (appointer_type = N'个人' AND appointer_dept_id IS NULL AND appointer_person_id IS NOT NULL AND appointer_house_id IS NULL) OR
        (appointer_type = N'房屋' AND appointer_dept_id IS NULL AND appointer_person_id IS NULL AND appointer_house_id IS NOT NULL)
    )
);

CREATE TABLE dbo.t_violation (
    violation_id INT IDENTITY(1,1) NOT NULL CONSTRAINT pk_violation PRIMARY KEY,
    vehicle_id INT NOT NULL,
    appointment_id INT NULL,
    rule_code NVARCHAR(20) NOT NULL,
    violation_time DATETIME2(0) NOT NULL,
    location NVARCHAR(200) NOT NULL,
    speed SMALLINT NULL,
    speed_limit SMALLINT NULL,
    evidence_path NVARCHAR(500) NULL,
    source NVARCHAR(20) NOT NULL,
    status NVARCHAR(10) NOT NULL CONSTRAINT df_violation_status DEFAULT N'已确认',
    remark NVARCHAR(500) NULL,
    created_at DATETIME2(0) NOT NULL CONSTRAINT df_violation_created_at DEFAULT SYSDATETIME(),
    CONSTRAINT fk_violation_vehicle FOREIGN KEY (vehicle_id) REFERENCES dbo.t_vehicle(vehicle_id),
    CONSTRAINT fk_violation_appointment FOREIGN KEY (appointment_id) REFERENCES dbo.t_appointment(appointment_id),
    CONSTRAINT fk_violation_rule FOREIGN KEY (rule_code) REFERENCES dbo.t_violation_rule(rule_code),
    CONSTRAINT ck_violation_source CHECK (source IN (N'摄像头', N'人工巡查', N'门禁系统', N'群众举报', N'其他')),
    CONSTRAINT ck_violation_status CHECK (status IN (N'已确认', N'申诉中', N'已撤销'))
);

CREATE TABLE dbo.t_appeal (
    appeal_id INT IDENTITY(1,1) NOT NULL CONSTRAINT pk_appeal PRIMARY KEY,
    violation_id INT NOT NULL,
    applicant_id INT NOT NULL,
    reason NVARCHAR(500) NOT NULL,
    evidence_path NVARCHAR(500) NULL,
    status NVARCHAR(10) NOT NULL CONSTRAINT df_appeal_status DEFAULT N'待处理',
    handler_id INT NULL,
    handler_opinion NVARCHAR(500) NULL,
    applied_at DATETIME2(0) NOT NULL CONSTRAINT df_appeal_applied_at DEFAULT SYSDATETIME(),
    handled_at DATETIME2(0) NULL,
    CONSTRAINT fk_appeal_violation FOREIGN KEY (violation_id) REFERENCES dbo.t_violation(violation_id),
    CONSTRAINT fk_appeal_applicant FOREIGN KEY (applicant_id) REFERENCES dbo.t_registrant(registrant_id),
    CONSTRAINT fk_appeal_handler FOREIGN KEY (handler_id) REFERENCES dbo.t_user(user_id),
    CONSTRAINT ck_appeal_status CHECK (status IN (N'待处理', N'已通过', N'已驳回', N'已撤回'))
);

CREATE TABLE dbo.t_scoring_period (
    period_id INT IDENTITY(1,1) NOT NULL CONSTRAINT pk_scoring_period PRIMARY KEY,
    vehicle_id INT NOT NULL,
    [year] SMALLINT NOT NULL,
    initial_points INT NOT NULL CONSTRAINT df_scoring_period_initial_points DEFAULT 12,
    deducted_points_total INT NOT NULL CONSTRAINT df_scoring_period_deducted DEFAULT 0,
    added_points_total INT NOT NULL CONSTRAINT df_scoring_period_added DEFAULT 0,
    add_count TINYINT NOT NULL CONSTRAINT df_scoring_period_add_count DEFAULT 0,
    remaining_points AS (
        CONVERT(INT, CASE
            WHEN initial_points + added_points_total - deducted_points_total < 0 THEN 0
            ELSE initial_points + added_points_total - deducted_points_total
        END)
    ) PERSISTED,
    has_danger_violation BIT NOT NULL CONSTRAINT df_scoring_period_has_danger DEFAULT 0,
    is_active BIT NOT NULL CONSTRAINT df_scoring_period_is_active DEFAULT 1,
    created_at DATETIME2(0) NOT NULL CONSTRAINT df_scoring_period_created_at DEFAULT SYSDATETIME(),
    CONSTRAINT fk_scoring_period_vehicle FOREIGN KEY (vehicle_id) REFERENCES dbo.t_vehicle(vehicle_id),
    CONSTRAINT uq_scoring_period_vehicle_year UNIQUE (vehicle_id, [year]),
    CONSTRAINT ck_scoring_period_year CHECK ([year] BETWEEN 2020 AND 2099),
    CONSTRAINT ck_scoring_period_points CHECK (
        initial_points >= 0 AND deducted_points_total >= 0 AND added_points_total >= 0 AND add_count BETWEEN 0 AND 2
    )
);

CREATE TABLE dbo.t_points_addition_log (
    addition_id INT IDENTITY(1,1) NOT NULL CONSTRAINT pk_points_addition_log PRIMARY KEY,
    period_id INT NOT NULL,
    vehicle_id INT NOT NULL,
    applicant_id INT NOT NULL,
    addition_points INT NOT NULL CONSTRAINT df_points_addition_points DEFAULT 12,
    proof_path NVARCHAR(500) NULL,
    status NVARCHAR(10) NOT NULL CONSTRAINT df_points_addition_status DEFAULT N'待审批',
    approver_id INT NULL,
    approver_opinion NVARCHAR(500) NULL,
    applied_at DATETIME2(0) NOT NULL CONSTRAINT df_points_addition_applied_at DEFAULT SYSDATETIME(),
    approved_at DATETIME2(0) NULL,
    CONSTRAINT fk_points_addition_period FOREIGN KEY (period_id) REFERENCES dbo.t_scoring_period(period_id),
    CONSTRAINT fk_points_addition_vehicle FOREIGN KEY (vehicle_id) REFERENCES dbo.t_vehicle(vehicle_id),
    CONSTRAINT fk_points_addition_applicant FOREIGN KEY (applicant_id) REFERENCES dbo.t_registrant(registrant_id),
    CONSTRAINT fk_points_addition_approver FOREIGN KEY (approver_id) REFERENCES dbo.t_user(user_id),
    CONSTRAINT ck_points_addition_points CHECK (addition_points > 0),
    CONSTRAINT ck_points_addition_status CHECK (status IN (N'待审批', N'已通过', N'已驳回', N'已撤回'))
);

CREATE TABLE dbo.t_penalty (
    penalty_id INT IDENTITY(1,1) NOT NULL CONSTRAINT pk_penalty PRIMARY KEY,
    violation_id INT NULL,
    source_vehicle_id INT NULL,
    period_id INT NULL,
    trigger_type NVARCHAR(20) NOT NULL,
    penalty_type NVARCHAR(20) NOT NULL,
    points_deducted INT NOT NULL CONSTRAINT df_penalty_points DEFAULT 0,
    suspension_days INT NULL,
    start_date DATE NULL,
    end_date DATE NULL,
    target_vehicle_id INT NULL,
    target_dept_id INT NULL,
    target_person_id INT NULL,
    target_house_id INT NULL,
    status NVARCHAR(10) NOT NULL CONSTRAINT df_penalty_status DEFAULT N'执行中',
    created_at DATETIME2(0) NOT NULL CONSTRAINT df_penalty_created_at DEFAULT SYSDATETIME(),
    CONSTRAINT fk_penalty_violation FOREIGN KEY (violation_id) REFERENCES dbo.t_violation(violation_id),
    CONSTRAINT fk_penalty_source_vehicle FOREIGN KEY (source_vehicle_id) REFERENCES dbo.t_vehicle(vehicle_id),
    CONSTRAINT fk_penalty_period FOREIGN KEY (period_id) REFERENCES dbo.t_scoring_period(period_id),
    CONSTRAINT fk_penalty_target_vehicle FOREIGN KEY (target_vehicle_id) REFERENCES dbo.t_vehicle(vehicle_id),
    CONSTRAINT fk_penalty_target_dept FOREIGN KEY (target_dept_id) REFERENCES dbo.t_department(department_id),
    CONSTRAINT fk_penalty_target_person FOREIGN KEY (target_person_id) REFERENCES dbo.t_registrant(registrant_id),
    CONSTRAINT fk_penalty_target_house FOREIGN KEY (target_house_id) REFERENCES dbo.t_house(house_id),
    CONSTRAINT ck_penalty_trigger_type CHECK (trigger_type IN (N'单次违规', N'累计扣分', N'恶性行为', N'人工处理')),
    CONSTRAINT ck_penalty_type CHECK (penalty_type IN (
        N'扣分', N'暂停入校', N'通报单位', N'谈话提醒', N'预约黑名单',
        N'暂停因私预约', N'取消房屋预约', N'永久禁止', N'全校通报'
    )),
    CONSTRAINT ck_penalty_status CHECK (status IN (N'待执行', N'执行中', N'已完成', N'已撤销')),
    CONSTRAINT ck_penalty_points CHECK (points_deducted >= 0),
    CONSTRAINT ck_penalty_suspension_days CHECK (suspension_days IS NULL OR suspension_days > 0),
    CONSTRAINT ck_penalty_date CHECK (end_date IS NULL OR start_date IS NULL OR end_date >= start_date),
    CONSTRAINT ck_penalty_single_target CHECK (
        (CASE WHEN target_vehicle_id IS NULL THEN 0 ELSE 1 END) +
        (CASE WHEN target_dept_id IS NULL THEN 0 ELSE 1 END) +
        (CASE WHEN target_person_id IS NULL THEN 0 ELSE 1 END) +
        (CASE WHEN target_house_id IS NULL THEN 0 ELSE 1 END) = 1
    )
);

CREATE TABLE dbo.t_blacklist (
    blacklist_id INT IDENTITY(1,1) NOT NULL CONSTRAINT pk_blacklist PRIMARY KEY,
    vehicle_id INT NOT NULL,
    blacklist_type NVARCHAR(10) NOT NULL,
    reason NVARCHAR(500) NOT NULL,
    source_type NVARCHAR(20) NOT NULL,
    penalty_id INT NULL,
    start_date DATE NOT NULL,
    end_date DATE NULL,
    is_active BIT NOT NULL CONSTRAINT df_blacklist_is_active DEFAULT 1,
    created_at DATETIME2(0) NOT NULL CONSTRAINT df_blacklist_created_at DEFAULT SYSDATETIME(),
    CONSTRAINT fk_blacklist_vehicle FOREIGN KEY (vehicle_id) REFERENCES dbo.t_vehicle(vehicle_id),
    CONSTRAINT fk_blacklist_penalty FOREIGN KEY (penalty_id) REFERENCES dbo.t_penalty(penalty_id),
    CONSTRAINT ck_blacklist_type CHECK (blacklist_type IN (N'临时', N'永久')),
    CONSTRAINT ck_blacklist_date CHECK (end_date IS NULL OR end_date >= start_date)
);

CREATE TABLE dbo.t_b_appointer_violation_summary (
    summary_id INT IDENTITY(1,1) NOT NULL CONSTRAINT pk_b_appointer_violation_summary PRIMARY KEY,
    appointer_type NVARCHAR(10) NOT NULL,
    appointer_dept_id INT NULL,
    appointer_person_id INT NULL,
    appointer_house_id INT NULL,
    [year] SMALLINT NOT NULL,
    accumulated_points INT NOT NULL CONSTRAINT df_b_summary_points DEFAULT 0,
    last_violation_time DATETIME2(0) NULL,
    penalty_triggered BIT NOT NULL CONSTRAINT df_b_summary_penalty_triggered DEFAULT 0,
    CONSTRAINT fk_b_summary_dept FOREIGN KEY (appointer_dept_id) REFERENCES dbo.t_department(department_id),
    CONSTRAINT fk_b_summary_person FOREIGN KEY (appointer_person_id) REFERENCES dbo.t_registrant(registrant_id),
    CONSTRAINT fk_b_summary_house FOREIGN KEY (appointer_house_id) REFERENCES dbo.t_house(house_id),
    CONSTRAINT ck_b_summary_type CHECK (appointer_type IN (N'单位', N'个人', N'房屋')),
    CONSTRAINT ck_b_summary_year CHECK ([year] BETWEEN 2020 AND 2099),
    CONSTRAINT ck_b_summary_points CHECK (accumulated_points >= 0),
    CONSTRAINT ck_b_summary_appointer CHECK (
        (appointer_type = N'单位' AND appointer_dept_id IS NOT NULL AND appointer_person_id IS NULL AND appointer_house_id IS NULL) OR
        (appointer_type = N'个人' AND appointer_dept_id IS NULL AND appointer_person_id IS NOT NULL AND appointer_house_id IS NULL) OR
        (appointer_type = N'房屋' AND appointer_dept_id IS NULL AND appointer_person_id IS NULL AND appointer_house_id IS NOT NULL)
    )
);

CREATE TABLE dbo.t_notification_log (
    notification_id INT IDENTITY(1,1) NOT NULL CONSTRAINT pk_notification_log PRIMARY KEY,
    vehicle_id INT NULL,
    violation_id INT NULL,
    penalty_id INT NULL,
    notification_type NVARCHAR(20) NOT NULL,
    recipient NVARCHAR(100) NOT NULL,
    recipient_type NVARCHAR(20) NOT NULL,
    content NVARCHAR(MAX) NOT NULL,
    sent_time DATETIME2(0) NULL,
    send_status NVARCHAR(10) NOT NULL CONSTRAINT df_notification_status DEFAULT N'待发送',
    created_at DATETIME2(0) NOT NULL CONSTRAINT df_notification_created_at DEFAULT SYSDATETIME(),
    CONSTRAINT fk_notification_vehicle FOREIGN KEY (vehicle_id) REFERENCES dbo.t_vehicle(vehicle_id),
    CONSTRAINT fk_notification_violation FOREIGN KEY (violation_id) REFERENCES dbo.t_violation(violation_id),
    CONSTRAINT fk_notification_penalty FOREIGN KEY (penalty_id) REFERENCES dbo.t_penalty(penalty_id),
    CONSTRAINT ck_notification_status CHECK (send_status IN (N'待发送', N'已发送', N'发送失败'))
);

CREATE TABLE dbo.t_notification_recipient (
    recipient_id INT IDENTITY(1,1) NOT NULL CONSTRAINT pk_notification_recipient PRIMARY KEY,
    role_label NVARCHAR(20) NOT NULL,
    department_id INT NULL,
    name NVARCHAR(50) NOT NULL,
    phone NVARCHAR(20) NOT NULL,
    is_active BIT NOT NULL CONSTRAINT df_notification_recipient_is_active DEFAULT 1,
    updated_at DATETIME2(0) NOT NULL CONSTRAINT df_notification_recipient_updated_at DEFAULT SYSDATETIME(),
    CONSTRAINT fk_notification_recipient_department FOREIGN KEY (department_id) REFERENCES dbo.t_department(department_id)
);

CREATE TABLE dbo.t_ai_query_template (
    template_id INT IDENTITY(1,1) NOT NULL CONSTRAINT pk_ai_query_template PRIMARY KEY,
    template_name NVARCHAR(100) NOT NULL CONSTRAINT uq_ai_query_template_name UNIQUE,
    description NVARCHAR(300) NULL,
    safe_sql NVARCHAR(MAX) NOT NULL,
    allowed_role NVARCHAR(20) NOT NULL,
    is_active BIT NOT NULL CONSTRAINT df_ai_template_is_active DEFAULT 1,
    created_at DATETIME2(0) NOT NULL CONSTRAINT df_ai_template_created_at DEFAULT SYSDATETIME()
);

CREATE TABLE dbo.t_ai_query_log (
    query_id INT IDENTITY(1,1) NOT NULL CONSTRAINT pk_ai_query_log PRIMARY KEY,
    requester_user_id INT NOT NULL,
    natural_language_question NVARCHAR(1000) NOT NULL,
    generated_sql NVARCHAR(MAX) NOT NULL,
    is_readonly BIT NOT NULL CONSTRAINT df_ai_query_is_readonly DEFAULT 1,
    execution_status NVARCHAR(10) NOT NULL CONSTRAINT df_ai_query_status DEFAULT N'待审核',
    rows_returned INT NULL,
    error_message NVARCHAR(1000) NULL,
    executed_at DATETIME2(0) NULL,
    created_at DATETIME2(0) NOT NULL CONSTRAINT df_ai_query_created_at DEFAULT SYSDATETIME(),
    CONSTRAINT fk_ai_query_user FOREIGN KEY (requester_user_id) REFERENCES dbo.t_user(user_id),
    CONSTRAINT ck_ai_query_status CHECK (execution_status IN (N'待审核', N'已执行', N'已拒绝', N'执行失败')),
    CONSTRAINT ck_ai_query_rows CHECK (rows_returned IS NULL OR rows_returned >= 0)
);
GO

-- ========== 3. 创建索引 ==========
CREATE INDEX ix_vehicle_registrant_type ON dbo.t_vehicle(registrant_id, vehicle_type);
CREATE INDEX ix_vehicle_status_end_date ON dbo.t_vehicle(register_status, status_end_date);
CREATE INDEX ix_vehicle_application_status ON dbo.t_vehicle_registration_application(apply_status, applied_at);
CREATE INDEX ix_vehicle_permit_vehicle_status ON dbo.t_vehicle_permit(vehicle_id, permit_status, valid_from, valid_to);
CREATE INDEX ix_appointment_plate_status_time ON dbo.t_appointment(plate_number, status, start_time, end_time);
CREATE INDEX ix_appointment_vehicle_time ON dbo.t_appointment(vehicle_id, start_time, end_time);
CREATE INDEX ix_violation_vehicle_time ON dbo.t_violation(vehicle_id, violation_time);
CREATE INDEX ix_violation_time ON dbo.t_violation(violation_time);
CREATE INDEX ix_violation_rule ON dbo.t_violation(rule_code);
CREATE INDEX ix_appeal_status_handler ON dbo.t_appeal(status, handler_id);
CREATE INDEX ix_scoring_period_active ON dbo.t_scoring_period(vehicle_id, is_active);
CREATE INDEX ix_points_addition_status ON dbo.t_points_addition_log(status, applied_at);
CREATE INDEX ix_penalty_target_vehicle_status ON dbo.t_penalty(target_vehicle_id, status);
CREATE INDEX ix_penalty_source_vehicle_status ON dbo.t_penalty(source_vehicle_id, status);
CREATE INDEX ix_blacklist_vehicle_active ON dbo.t_blacklist(vehicle_id, is_active);
CREATE UNIQUE INDEX uq_blacklist_vehicle_active ON dbo.t_blacklist(vehicle_id) WHERE is_active = 1;
CREATE UNIQUE INDEX uq_b_summary_dept_year ON dbo.t_b_appointer_violation_summary(appointer_dept_id, [year])
    WHERE appointer_type = N'单位' AND appointer_dept_id IS NOT NULL;
CREATE UNIQUE INDEX uq_b_summary_person_year ON dbo.t_b_appointer_violation_summary(appointer_person_id, [year])
    WHERE appointer_type = N'个人' AND appointer_person_id IS NOT NULL;
CREATE UNIQUE INDEX uq_b_summary_house_year ON dbo.t_b_appointer_violation_summary(appointer_house_id, [year])
    WHERE appointer_type = N'房屋' AND appointer_house_id IS NOT NULL;
CREATE INDEX ix_notification_status ON dbo.t_notification_log(send_status, created_at);
CREATE INDEX ix_notification_recipient_role ON dbo.t_notification_recipient(role_label, is_active);
CREATE INDEX ix_ai_query_user_time ON dbo.t_ai_query_log(requester_user_id, created_at);
GO