/*
  Mock data for the campus smart traffic management database.
  Run after 01_schema_sqlserver.sql on an empty database.
*/

USE SchoolDB;
GO

SET XACT_ABORT ON;
BEGIN TRANSACTION;

INSERT INTO dbo.t_department (dept_name, dept_type, contact_name, contact_phone) VALUES
(N'保卫处', N'行政', N'周老师', N'13800000001'),
(N'信息学院', N'教学', N'刘老师', N'13800000002'),
(N'后勤服务中心', N'后勤', N'孙老师', N'13800000003'),
(N'图书馆', N'其他', N'吴老师', N'13800000004');

INSERT INTO dbo.t_house (house_code, address, owner_name, owner_phone, appointment_status, appointment_suspend_until) VALUES
(N'GH-A-101', N'光华校区家属区 A 栋 101', N'王强', N'13900000001', N'正常', NULL),
(N'GH-B-202', N'光华校区家属区 B 栋 202', N'赵倩', N'13900000002', N'暂停', '2026-06-30');

DECLARE @dept_security INT = (SELECT department_id FROM dbo.t_department WHERE dept_name = N'保卫处');
DECLARE @dept_info INT = (SELECT department_id FROM dbo.t_department WHERE dept_name = N'信息学院');
DECLARE @dept_logistics INT = (SELECT department_id FROM dbo.t_department WHERE dept_name = N'后勤服务中心');
DECLARE @dept_library INT = (SELECT department_id FROM dbo.t_department WHERE dept_name = N'图书馆');
DECLARE @house_101 INT = (SELECT house_id FROM dbo.t_house WHERE house_code = N'GH-A-101');
DECLARE @house_202 INT = (SELECT house_id FROM dbo.t_house WHERE house_code = N'GH-B-202');

INSERT INTO dbo.t_registrant
    (name, identity_type, department_id, house_id, phone, id_number, appointment_status, appointment_suspend_until)
VALUES
(N'张明', N'教职工', @dept_info, NULL, N'13600000001', N'T2026001', N'正常', NULL),
(N'李华', N'学生', @dept_info, NULL, N'13600000002', N'S2026001', N'正常', NULL),
(N'王强', N'购租户', NULL, @house_101, N'13600000003', N'H2026001', N'正常', NULL),
(N'赵倩', N'购租户', NULL, @house_202, N'13600000004', N'H2026002', N'正常', NULL),
(N'陈师傅', N'外来人员', @dept_logistics, NULL, N'13600000005', N'EXT2026001', N'正常', NULL),
(N'周访客', N'外来人员', NULL, NULL, N'13600000006', N'EXT2026002', N'暂停', '2026-06-25');

DECLARE @reg_zhang INT = (SELECT registrant_id FROM dbo.t_registrant WHERE name = N'张明' AND phone = N'13600000001');
DECLARE @reg_li INT = (SELECT registrant_id FROM dbo.t_registrant WHERE name = N'李华' AND phone = N'13600000002');
DECLARE @reg_wang INT = (SELECT registrant_id FROM dbo.t_registrant WHERE name = N'王强' AND phone = N'13600000003');
DECLARE @reg_zhao INT = (SELECT registrant_id FROM dbo.t_registrant WHERE name = N'赵倩' AND phone = N'13600000004');
DECLARE @reg_chen INT = (SELECT registrant_id FROM dbo.t_registrant WHERE name = N'陈师傅' AND phone = N'13600000005');
DECLARE @reg_visitor INT = (SELECT registrant_id FROM dbo.t_registrant WHERE name = N'周访客' AND phone = N'13600000006');

INSERT INTO dbo.t_user (username, password_hash, real_name, role, phone, department_id, registrant_id) VALUES
(N'admin', N'FAKE_HASH_FOR_DEMO_ONLY', N'系统管理员', N'系统管理员', N'13700000001', @dept_security, NULL),
(N'security01', N'FAKE_HASH_FOR_DEMO_ONLY', N'周老师', N'保卫处管理员', N'13700000002', @dept_security, NULL),
(N'auditor01', N'FAKE_HASH_FOR_DEMO_ONLY', N'审核员王', N'审核员', N'13700000003', @dept_security, NULL),
(N'zhangming', N'FAKE_HASH_FOR_DEMO_ONLY', N'张明', N'车主', N'13600000001', @dept_info, @reg_zhang),
(N'info_contact', N'FAKE_HASH_FOR_DEMO_ONLY', N'刘老师', N'单位联系人', N'13800000002', @dept_info, NULL);

DECLARE @user_security INT = (SELECT user_id FROM dbo.t_user WHERE username = N'security01');
DECLARE @user_auditor INT = (SELECT user_id FROM dbo.t_user WHERE username = N'auditor01');
DECLARE @user_owner_zhang INT = (SELECT user_id FROM dbo.t_user WHERE username = N'zhangming');

INSERT INTO dbo.t_vehicle (plate_number, vehicle_type, registrant_id, register_status, register_date, status_start_date, status_end_date, remark) VALUES
(N'川A12345', 'A', @reg_zhang, N'暂停', '2026-01-10 09:30:00', '2026-06-12', '2026-08-10', N'危险超速后暂停入校 60 天'),
(N'川B23456', 'A', @reg_li, N'正常', '2026-02-18 14:20:00', NULL, NULL, N'学生固定车辆'),
(N'川C34567', 'C', @reg_wang, N'正常', '2026-03-05 10:00:00', NULL, NULL, N'购租户摩托车'),
(N'川D45678', 'B', @reg_chen, N'正常', '2026-05-20 08:00:00', NULL, NULL, N'后勤送货预约车辆'),
(N'川E56789', 'B', @reg_visitor, N'正常', '2026-05-21 08:00:00', NULL, NULL, N'因私探访预约车辆'),
(N'川F67890', 'B', @reg_zhao, N'正常', '2026-05-22 08:00:00', NULL, NULL, N'购租户预约车辆');

DECLARE @veh_a_zhang INT = (SELECT vehicle_id FROM dbo.t_vehicle WHERE plate_number = N'川A12345');
DECLARE @veh_a_li INT = (SELECT vehicle_id FROM dbo.t_vehicle WHERE plate_number = N'川B23456');
DECLARE @veh_c_wang INT = (SELECT vehicle_id FROM dbo.t_vehicle WHERE plate_number = N'川C34567');
DECLARE @veh_b_delivery INT = (SELECT vehicle_id FROM dbo.t_vehicle WHERE plate_number = N'川D45678');
DECLARE @veh_b_private INT = (SELECT vehicle_id FROM dbo.t_vehicle WHERE plate_number = N'川E56789');
DECLARE @veh_b_house INT = (SELECT vehicle_id FROM dbo.t_vehicle WHERE plate_number = N'川F67890');

INSERT INTO dbo.t_vehicle_registration_application
    (vehicle_id, applicant_registrant_id, plate_number, vehicle_type, apply_type, apply_reason, material_path, apply_status, reviewer_id, review_opinion, applied_at, reviewed_at)
VALUES
(@veh_a_zhang, @reg_zhang, N'川A12345', 'A', N'注册', N'教职工固定车辆入校通行', N'/demo/materials/a12345.pdf', N'已通过', @user_auditor, N'材料齐全，同意注册', '2026-01-08 10:00:00', '2026-01-09 15:00:00'),
(@veh_a_li, @reg_li, N'川B23456', 'A', N'注册', N'学生固定车辆入校通行', N'/demo/materials/b23456.pdf', N'已通过', @user_auditor, N'材料齐全，同意注册', '2026-02-16 10:00:00', '2026-02-17 15:00:00'),
(@veh_c_wang, @reg_wang, N'川C34567', 'C', N'注册', N'购租户摩托车备案', N'/demo/materials/c34567.pdf', N'已通过', @user_auditor, N'同意备案', '2026-03-03 09:00:00', '2026-03-04 11:00:00'),
(@veh_b_delivery, @reg_chen, N'川D45678', 'B', N'注册', N'后勤配送临时车建档', NULL, N'已通过', @user_auditor, N'建档用于预约管理', '2026-05-19 09:00:00', '2026-05-19 11:00:00');

DECLARE @app_a_zhang INT = (SELECT application_id FROM dbo.t_vehicle_registration_application WHERE plate_number = N'川A12345');
DECLARE @app_a_li INT = (SELECT application_id FROM dbo.t_vehicle_registration_application WHERE plate_number = N'川B23456');
DECLARE @app_c_wang INT = (SELECT application_id FROM dbo.t_vehicle_registration_application WHERE plate_number = N'川C34567');
DECLARE @app_b_delivery INT = (SELECT application_id FROM dbo.t_vehicle_registration_application WHERE plate_number = N'川D45678');

INSERT INTO dbo.t_vehicle_permit
    (vehicle_id, application_id, permit_type, valid_from, valid_to, permit_status, issued_by, issued_at)
VALUES
(@veh_a_zhang, @app_a_zhang, N'固定通行', '2026-01-10', '2026-12-31', N'暂停', @user_auditor, '2026-01-09 15:05:00'),
(@veh_a_li, @app_a_li, N'固定通行', '2026-02-18', '2026-12-31', N'有效', @user_auditor, '2026-02-17 15:05:00'),
(@veh_c_wang, @app_c_wang, N'摩托车通行', '2026-03-05', '2026-12-31', N'有效', @user_auditor, '2026-03-04 11:05:00'),
(@veh_b_delivery, @app_b_delivery, N'临时预约', '2026-05-20', '2026-06-30', N'有效', @user_auditor, '2026-05-19 11:05:00');

INSERT INTO dbo.t_violation_rule
    (rule_code, violation_type, violation_level, points_deducted, speed_min, speed_max, is_malicious, description)
VALUES
(N'SPD-MINOR', N'超速', N'轻微超速', 0, 30, 40, 0, N'30 < speed <= 40'),
(N'SPD-GENERAL', N'超速', N'一般超速', 1, 41, 50, 0, N'40 < speed <= 50'),
(N'SPD-SEVERE', N'超速', N'严重超速', 3, 51, 60, 0, N'50 < speed <= 60'),
(N'SPD-DANGER', N'超速', N'危险超速', 12, 61, NULL, 0, N'speed >= 61，触发 60 天暂停和全校通报'),
(N'PRK-NORMAL', N'违停', N'普通违停', 1, NULL, NULL, 0, N'普通违停'),
(N'PRK-SEVERE', N'违停', N'严重违停', 3, NULL, NULL, 0, N'严重违停'),
(N'PRK-DANGER', N'违停', N'危险违停', 12, NULL, NULL, 0, N'危险违停'),
(N'MAL-DRUNK', N'醉酒驾驶', N'醉酒驾驶', 0, NULL, NULL, 1, N'恶性行为，视情况永久禁止入校'),
(N'MAL-HITRUN', N'肇事逃逸', N'肇事逃逸', 0, NULL, NULL, 1, N'恶性行为，视情况永久禁止入校'),
(N'MAL-OTHER', N'其他恶性行为', N'其他恶性行为', 0, NULL, NULL, 1, N'其他恶性行为');

INSERT INTO dbo.t_appointment
    (vehicle_id, plate_number, appointer_type, appointer_dept_id, appointer_person_id, appointer_house_id, purpose, start_time, end_time, status, approver_id, approved_at)
VALUES
(@veh_b_delivery, N'川D45678', N'单位', @dept_logistics, NULL, NULL, N'食堂物资配送', '2026-06-10 08:00:00', '2026-06-10 12:00:00', N'已通过', @user_security, '2026-06-09 16:00:00'),
(@veh_b_private, N'川E56789', N'个人', NULL, @reg_visitor, NULL, N'探访信息学院教师', '2026-06-11 14:00:00', '2026-06-11 18:00:00', N'已通过', @user_security, '2026-06-11 09:00:00'),
(@veh_b_house, N'川F67890', N'房屋', NULL, NULL, @house_202, N'购租户搬运物品', '2026-06-12 09:00:00', '2026-06-12 17:00:00', N'已通过', @user_security, '2026-06-12 08:30:00');

DECLARE @appt_delivery INT = (SELECT appointment_id FROM dbo.t_appointment WHERE plate_number = N'川D45678');
DECLARE @appt_private INT = (SELECT appointment_id FROM dbo.t_appointment WHERE plate_number = N'川E56789');
DECLARE @appt_house INT = (SELECT appointment_id FROM dbo.t_appointment WHERE plate_number = N'川F67890');

INSERT INTO dbo.t_violation
    (vehicle_id, appointment_id, rule_code, violation_time, location, speed, speed_limit, evidence_path, source, status, remark)
VALUES
(@veh_a_zhang, NULL, N'SPD-GENERAL', '2026-04-08 08:35:00', N'柳林大道东门段', 46, 30, N'/demo/evidence/v001.jpg', N'摄像头', N'已确认', N'A 类车一般超速'),
(@veh_a_zhang, NULL, N'SPD-DANGER', '2026-06-12 17:20:00', N'光华大道西门段', 68, 30, N'/demo/evidence/v002.jpg', N'摄像头', N'已确认', N'A 类车危险超速'),
(@veh_b_delivery, @appt_delivery, N'PRK-SEVERE', '2026-06-10 10:30:00', N'食堂后门消防通道', NULL, NULL, N'/demo/evidence/v003.jpg', N'人工巡查', N'已确认', N'后勤预约车辆严重违停'),
(@veh_b_private, @appt_private, N'PRK-NORMAL', '2026-06-11 15:10:00', N'信息楼临停区外', NULL, NULL, N'/demo/evidence/v004.jpg', N'人工巡查', N'申诉中', N'因私预约车辆普通违停，车主已申诉'),
(@veh_b_house, @appt_house, N'PRK-DANGER', '2026-06-12 11:15:00', N'消防通道主入口', NULL, NULL, N'/demo/evidence/v005.jpg', N'人工巡查', N'已确认', N'购租户预约车辆危险违停'),
(@veh_c_wang, NULL, N'PRK-SEVERE', '2026-05-28 09:40:00', N'教学楼前人行道', NULL, NULL, N'/demo/evidence/v006.jpg', N'群众举报', N'已确认', N'C 类摩托车严重违停');

DECLARE @vio_a_general INT = (SELECT violation_id FROM dbo.t_violation WHERE evidence_path = N'/demo/evidence/v001.jpg');
DECLARE @vio_a_danger INT = (SELECT violation_id FROM dbo.t_violation WHERE evidence_path = N'/demo/evidence/v002.jpg');
DECLARE @vio_b_delivery INT = (SELECT violation_id FROM dbo.t_violation WHERE evidence_path = N'/demo/evidence/v003.jpg');
DECLARE @vio_b_private INT = (SELECT violation_id FROM dbo.t_violation WHERE evidence_path = N'/demo/evidence/v004.jpg');
DECLARE @vio_b_house INT = (SELECT violation_id FROM dbo.t_violation WHERE evidence_path = N'/demo/evidence/v005.jpg');
DECLARE @vio_c_wang INT = (SELECT violation_id FROM dbo.t_violation WHERE evidence_path = N'/demo/evidence/v006.jpg');

INSERT INTO dbo.t_scoring_period
    (vehicle_id, [year], initial_points, deducted_points_total, added_points_total, add_count, has_danger_violation, is_active)
VALUES
(@veh_a_zhang, 2026, 12, 13, 0, 0, 1, 1),
(@veh_a_li, 2026, 12, 0, 0, 0, 0, 1),
(@veh_c_wang, 2026, 12, 3, 0, 0, 0, 1),
(@veh_b_delivery, 2026, 12, 3, 0, 0, 0, 1),
(@veh_b_private, 2026, 12, 1, 0, 0, 0, 1),
(@veh_b_house, 2026, 12, 12, 0, 0, 1, 1);

DECLARE @period_a_zhang INT = (SELECT period_id FROM dbo.t_scoring_period WHERE vehicle_id = @veh_a_zhang AND [year] = 2026);
DECLARE @period_c_wang INT = (SELECT period_id FROM dbo.t_scoring_period WHERE vehicle_id = @veh_c_wang AND [year] = 2026);
DECLARE @period_b_delivery INT = (SELECT period_id FROM dbo.t_scoring_period WHERE vehicle_id = @veh_b_delivery AND [year] = 2026);
DECLARE @period_b_private INT = (SELECT period_id FROM dbo.t_scoring_period WHERE vehicle_id = @veh_b_private AND [year] = 2026);
DECLARE @period_b_house INT = (SELECT period_id FROM dbo.t_scoring_period WHERE vehicle_id = @veh_b_house AND [year] = 2026);

INSERT INTO dbo.t_points_addition_log
    (period_id, vehicle_id, applicant_id, addition_points, proof_path, status, approver_id, approver_opinion, applied_at, approved_at)
VALUES
(@period_b_house, @veh_b_house, @reg_zhao, 12, N'/demo/proofs/study_f67890.pdf', N'已驳回', @user_auditor, N'B 类车辆不适用加分机制', '2026-06-13 09:00:00', '2026-06-13 15:30:00');

INSERT INTO dbo.t_penalty
    (violation_id, source_vehicle_id, period_id, trigger_type, penalty_type, points_deducted, suspension_days, start_date, end_date, target_vehicle_id, target_dept_id, target_person_id, target_house_id, status)
VALUES
(@vio_a_general, @veh_a_zhang, @period_a_zhang, N'单次违规', N'扣分', 1, NULL, '2026-04-08', NULL, @veh_a_zhang, NULL, NULL, NULL, N'已完成'),
(@vio_a_danger, @veh_a_zhang, @period_a_zhang, N'单次违规', N'暂停入校', 12, 60, '2026-06-12', '2026-08-10', @veh_a_zhang, NULL, NULL, NULL, N'执行中'),
(@vio_a_danger, @veh_a_zhang, @period_a_zhang, N'单次违规', N'全校通报', 0, NULL, '2026-06-12', NULL, @veh_a_zhang, NULL, NULL, NULL, N'已完成'),
(@vio_b_delivery, @veh_b_delivery, @period_b_delivery, N'单次违规', N'扣分', 3, NULL, '2026-06-10', NULL, @veh_b_delivery, NULL, NULL, NULL, N'已完成'),
(@vio_b_delivery, @veh_b_delivery, @period_b_delivery, N'累计扣分', N'通报单位', 0, NULL, '2026-06-10', NULL, NULL, @dept_logistics, NULL, NULL, N'已完成'),
(@vio_b_private, @veh_b_private, @period_b_private, N'单次违规', N'扣分', 1, NULL, '2026-06-11', NULL, @veh_b_private, NULL, NULL, NULL, N'待执行'),
(@vio_b_house, @veh_b_house, @period_b_house, N'单次违规', N'预约黑名单', 12, NULL, '2026-06-12', NULL, @veh_b_house, NULL, NULL, NULL, N'执行中'),
(@vio_b_house, @veh_b_house, @period_b_house, N'累计扣分', N'取消房屋预约', 0, 30, '2026-06-12', '2026-07-12', NULL, NULL, NULL, @house_202, N'执行中'),
(@vio_c_wang, @veh_c_wang, @period_c_wang, N'单次违规', N'扣分', 3, NULL, '2026-05-28', NULL, @veh_c_wang, NULL, NULL, NULL, N'已完成');

DECLARE @penalty_a_pause INT = (
    SELECT penalty_id FROM dbo.t_penalty
    WHERE violation_id = @vio_a_danger AND penalty_type = N'暂停入校'
);
DECLARE @penalty_b_blacklist INT = (
    SELECT penalty_id FROM dbo.t_penalty
    WHERE violation_id = @vio_b_house AND penalty_type = N'预约黑名单'
);

INSERT INTO dbo.t_blacklist
    (vehicle_id, blacklist_type, reason, source_type, penalty_id, start_date, end_date, is_active)
VALUES
(@veh_a_zhang, N'临时', N'危险超速，暂停入校 60 天', N'处罚触发', @penalty_a_pause, '2026-06-12', '2026-08-10', 1),
(@veh_b_house, N'永久', N'B 类预约车单车扣分达到预约黑名单阈值', N'处罚触发', @penalty_b_blacklist, '2026-06-12', NULL, 1);

INSERT INTO dbo.t_b_appointer_violation_summary
    (appointer_type, appointer_dept_id, appointer_person_id, appointer_house_id, [year], accumulated_points, last_violation_time, penalty_triggered)
VALUES
(N'单位', @dept_logistics, NULL, NULL, 2026, 24, '2026-06-10 10:30:00', 1),
(N'个人', NULL, @reg_visitor, NULL, 2026, 1, '2026-06-11 15:10:00', 0),
(N'房屋', NULL, NULL, @house_202, 2026, 12, '2026-06-12 11:15:00', 1);

INSERT INTO dbo.t_appeal
    (violation_id, applicant_id, reason, evidence_path, status, handler_id, handler_opinion, applied_at, handled_at)
VALUES
(@vio_b_private, @reg_visitor, N'车辆停靠时间短，且现场标识不清，请复核。', N'/demo/appeals/a004.pdf', N'待处理', @user_security, NULL, '2026-06-11 18:30:00', NULL),
(@vio_c_wang, @reg_wang, N'已按现场保安指引停放，请撤销处罚。', NULL, N'已驳回', @user_security, N'现场照片显示停放在人行道，维持原处罚。', '2026-05-29 09:00:00', '2026-05-30 10:15:00');

INSERT INTO dbo.t_notification_log
    (vehicle_id, violation_id, penalty_id, notification_type, recipient, recipient_type, content, sent_time, send_status)
VALUES
(@veh_a_zhang, @vio_a_danger, @penalty_a_pause, N'处罚通知', N'张明/13600000001', N'车主', N'您的车辆川A12345因危险超速被暂停入校60天。', '2026-06-12 18:00:00', N'已发送'),
(@veh_b_delivery, @vio_b_delivery, NULL, N'单位通报', N'后勤服务中心/13800000003', N'单位', N'后勤服务中心预约车辆年度累计扣分达到24分，予以通报。', '2026-06-10 16:30:00', N'已发送'),
(@veh_b_private, @vio_b_private, NULL, N'申诉受理', N'周访客/13600000006', N'车主', N'您的申诉已受理，请等待保卫处处理。', NULL, N'待发送');

INSERT INTO dbo.t_notification_recipient (role_label, department_id, name, phone, is_active) VALUES
(N'保卫处值班员', @dept_security, N'周老师', N'13800000001', 1),
(N'单位负责人', @dept_logistics, N'孙老师', N'13800000003', 1),
(N'单位负责人', @dept_info, N'刘老师', N'13800000002', 1);

INSERT INTO dbo.t_ai_query_template (template_name, description, safe_sql, allowed_role, is_active) VALUES
(N'按车牌查询车辆状态', N'门禁或管理员按车牌查询车辆、黑名单和有效预约状态。',
 N'SELECT v.plate_number, v.vehicle_type, v.register_status, v.status_end_date FROM dbo.t_vehicle AS v WHERE v.plate_number = @plate_number;',
 N'保卫处管理员', 1),
(N'统计月度违规', N'按月份和违规类型统计已确认违规数量。',
 N'SELECT FORMAT(v.violation_time, ''yyyy-MM'') AS month_key, r.violation_type, COUNT(*) AS violation_count FROM dbo.t_violation AS v JOIN dbo.t_violation_rule AS r ON v.rule_code = r.rule_code WHERE v.status = N''已确认'' GROUP BY FORMAT(v.violation_time, ''yyyy-MM''), r.violation_type;',
 N'保卫处管理员', 1);

INSERT INTO dbo.t_ai_query_log
    (requester_user_id, natural_language_question, generated_sql, is_readonly, execution_status, rows_returned, error_message, executed_at)
VALUES
(@user_security, N'查询川A12345现在能不能入校',
 N'SELECT v.plate_number, v.register_status, v.status_end_date, b.is_active FROM dbo.t_vehicle v LEFT JOIN dbo.t_blacklist b ON v.vehicle_id = b.vehicle_id AND b.is_active = 1 WHERE v.plate_number = N''川A12345'';',
 1, N'已执行', 1, NULL, '2026-06-16 10:00:00'),
(@user_owner_zhang, N'查询所有车辆的手机号',
 N'SELECT name, phone FROM dbo.t_registrant;',
 1, N'已拒绝', NULL, N'车主角色不能查询他人联系方式。', NULL);

COMMIT TRANSACTION;
