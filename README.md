# 校园机动车综合管理后台

本项目基于已有 SQL Server 表结构脚本构建：

- 后端：Python Flask + pyodbc，提供 REST API 并连接 SQL Server。
- 前端：Next.js + TypeScript + Tailwind CSS + Radix Dialog/Toast + lucide-react。

## 目录

- `01_schema_sqlserver.sql`：SQL Server 建表脚本。
- `02_seed_mock_data.sql`：模拟数据脚本。
- `backend/`：Flask 后端。
- `frontend/`：Next.js 前端。

## 数据库初始化

在 SQL Server 中先创建数据库，再执行脚本：

```sql
CREATE DATABASE SchoolDB;
GO
```

然后按顺序执行：

```text
01_schema_sqlserver.sql
02_seed_mock_data.sql
```

## 后端初始化启动

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

编辑 `backend/.env`，填入你的 SQL Server 地址、账号和密码。然后启动：

```powershell
python app.py
```

默认地址：`http://127.0.0.1:5001/api`



## 后端再次启动

```shell
cd backend
python app.py
```



## 前端初始化启动

```powershell
cd frontend
npm install
Copy-Item .env.local.example .env.local
npm run dev
```

默认地址：`http://localhost:3000`



## 前端再次启动

```shell
cd frontend
npm run dev
```

默认地址：`http://localhost:3000`



## 已实现的业务页面

- 运行概览与最新违规/处罚展示
- 车辆档案管理
- 预约入校管理
- 违规记录管理
- 处罚处理管理
- 申诉审批管理
- 黑名单管理
- 通知日志管理
- 门禁核验
- 查询智能体只读 SQL 执行与审计日志

## 连接测试

后端启动后可访问：

```text
GET http://127.0.0.1:5001/api/health
```

若返回数据库名和服务器时间，说明 Flask 与 SQL Server 连接正常。



## 补充

查询智能体审计演示部分：模拟一个“自然语言转 SQL 查询助手”，系统只允许它执行只读 SELECT，并把每次查询写入审计日志

这个接口只接受以 `SELECT` 开头的 SQL。如果输入 `INSERT`、`UPDATE`、`DELETE`、`DROP` 等语句，会被拒绝执行，并用于体现数据库安全审计设计。

使用步骤：

1. 选择请求用户
   在第一个下拉框里选一个用户，例如 `周老师 / 保卫处管理员`。

2. 输入自然语言问题
   例如：

```
查询当前所有被暂停或禁止入校的车辆
```

3. 输入对应的 SQL
   当前版本不会真正调用大模型自动生成 SQL，需要你手动填入一条 `SELECT` 查询。例如：

```
SELECT plate_number, vehicle_type, register_status, status_end_date
FROM dbo.t_vehicle
WHERE register_status IN (N'暂停', N'永久禁止');
```

4. 点击 `执行`
   页面会显示查询结果，并弹出操作提示。后端同时会把这次查询写入 `t_ai_query_log`。



可以试的示例 SQL：

```sql
SELECT plate_number, vehicle_type, register_status
FROM dbo.t_vehicle;


SELECT v.plate_number, r.violation_type, r.violation_level, tv.violation_time, tv.location
FROM dbo.t_violation AS tv
JOIN dbo.t_vehicle AS v ON v.vehicle_id = tv.vehicle_id
JOIN dbo.t_violation_rule AS r ON r.rule_code = tv.rule_code;


SELECT penalty_type, status, COUNT(*) AS count_value
FROM dbo.t_penalty
GROUP BY penalty_type, status;
```
