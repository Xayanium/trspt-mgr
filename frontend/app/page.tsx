"use client";

import * as Dialog from "@radix-ui/react-dialog";
import * as Toast from "@radix-ui/react-toast";
import {
  AlertTriangle,
  Bell,
  Bot,
  Car,
  Check,
  ClipboardCheck,
  Database,
  FilePenLine,
  Gauge,
  LayoutDashboard,
  ListFilter,
  LogOut,
  Loader2,
  Plus,
  RefreshCcw,
  Search,
  ShieldAlert,
  SquarePen,
  Trash2,
  UserRound,
  X
} from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { apiGet, apiSend } from "@/lib/api";

type Row = Record<string, string | number | boolean | null>;

type TablePayload = {
  items: Row[];
  total: number;
  limit: number;
  offset: number;
};

type OptionItem = {
  id: string | number;
  label: string;
};

type OptionsPayload = Record<string, OptionItem[]>;

type Field = {
  name: string;
  label: string;
  type?: "text" | "number" | "select" | "date" | "datetime-local" | "textarea";
  optionKey?: string;
  options?: OptionItem[];
  placeholder?: string;
};

type ResourceConfig = {
  key: string;
  title: string;
  icon: React.ElementType;
  columns: { key: string; label: string }[];
  fields: Field[];
  accent: string;
};

type DashboardPayload = {
  stats: Record<string, number>;
  latest_violations: Row[];
  active_penalties: Row[];
};

type CurrentUser = {
  user_id: number;
  username: string;
  real_name: string;
  role: string;
  department_id: number | null;
  registrant_id: number | null;
};

const adminRoles = new Set(["系统管理员", "保卫处管理员", "审核员"]);
const ownerResourceKeys = new Set(["vehicles", "appointments", "violations", "penalties", "appeals", "points-additions", "scoring-periods"]);

function isAdminUser(user: CurrentUser | null) {
  return !!user && adminRoles.has(user.role);
}

const resourceConfigs: ResourceConfig[] = [
  {
    key: "vehicles",
    title: "车辆档案",
    icon: Car,
    accent: "text-pine",
    columns: [
      { key: "vehicle_id", label: "ID" },
      { key: "plate_number", label: "车牌" },
      { key: "vehicle_type", label: "类型" },
      { key: "registrant_name", label: "登记人" },
      { key: "register_status", label: "状态" },
      { key: "register_date", label: "注册日期" },
      { key: "status_end_date", label: "截止日期" },
      { key: "remark", label: "备注" }
    ],
    fields: [
      { name: "plate_number", label: "车牌号", placeholder: "川A12345" },
      { name: "vehicle_type", label: "车辆类型", type: "select", options: [{ id: "A", label: "A 固定注册" }, { id: "B", label: "B 预约车辆" }, { id: "C", label: "C 摩托车" }] },
      { name: "registrant_id", label: "登记人", type: "select", optionKey: "registrants" },
      { name: "register_status", label: "注册状态", type: "select", options: [{ id: "待审批", label: "待审批" }, { id: "正常", label: "正常" }, { id: "暂停", label: "暂停" }, { id: "永久禁止", label: "永久禁止" }, { id: "注销", label: "注销" }] },
      { name: "status_start_date", label: "状态起始", type: "date" },
      { name: "status_end_date", label: "状态截止", type: "date" },
      { name: "remark", label: "备注", type: "textarea" }
    ]
  },
  {
    key: "appointments",
    title: "预约入校",
    icon: ClipboardCheck,
    accent: "text-cyan",
    columns: [
      { key: "appointment_id", label: "ID" },
      { key: "plate_number", label: "车牌" },
      { key: "appointer_display", label: "预约方" },
      { key: "purpose", label: "用途" },
      { key: "start_time", label: "开始" },
      { key: "status", label: "状态" }
    ],
    fields: [
      { name: "vehicle_id", label: "车辆", type: "select", optionKey: "vehicles" },
      { name: "plate_number", label: "车牌号" },
      { name: "appointer_type", label: "预约方类型", type: "select", options: [{ id: "单位", label: "单位" }, { id: "个人", label: "个人" }, { id: "房屋", label: "房屋" }] },
      { name: "appointer_dept_id", label: "预约单位", type: "select", optionKey: "departments" },
      { name: "appointer_person_id", label: "预约个人", type: "select", optionKey: "registrants" },
      { name: "appointer_house_id", label: "预约房屋", type: "select", optionKey: "houses" },
      { name: "purpose", label: "入校用途", type: "textarea" },
      { name: "start_time", label: "开始时间", type: "datetime-local" },
      { name: "end_time", label: "结束时间", type: "datetime-local" },
      { name: "status", label: "状态", type: "select", options: [{ id: "待审批", label: "待审批" }, { id: "已通过", label: "已通过" }, { id: "已驳回", label: "已驳回" }, { id: "已取消", label: "已取消" }, { id: "已过期", label: "已过期" }] },
      { name: "approver_id", label: "审批人", type: "select", optionKey: "users" }
    ]
  },
  {
    key: "violations",
    title: "违规记录",
    icon: ShieldAlert,
    accent: "text-berry",
    columns: [
      { key: "violation_id", label: "ID" },
      { key: "plate_number", label: "车牌号" },
      { key: "violation_type", label: "违规类型" },
      { key: "violation_level", label: "违规等级" },
      { key: "violation_time", label: "时间" },
      { key: "location", label: "地点" },
      { key: "speed", label: "实测速度" },
      { key: "speed_limit", label: "限速" },
      { key: "source", label: "来源" },
      { key: "status", label: "状态" },
      { key: "remark", label: "备注" }
    ],
    fields: [
      { name: "vehicle_id", label: "车辆", type: "select", optionKey: "vehicles" },
      { name: "appointment_id", label: "预约", type: "select", optionKey: "appointments" },
      { name: "rule_code", label: "违规规则", type: "select", optionKey: "rules" },
      { name: "violation_time", label: "违规时间", type: "datetime-local" },
      { name: "location", label: "地点" },
      { name: "speed", label: "实测速度", type: "number" },
      { name: "speed_limit", label: "限速", type: "number" },
      { name: "evidence_path", label: "证据路径" },
      { name: "source", label: "发现来源", type: "select", options: [{ id: "摄像头", label: "摄像头" }, { id: "人工巡查", label: "人工巡查" }, { id: "门禁系统", label: "门禁系统" }, { id: "群众举报", label: "群众举报" }, { id: "其他", label: "其他" }] },
      { name: "status", label: "状态", type: "select", options: [{ id: "已确认", label: "已确认" }, { id: "申诉中", label: "申诉中" }, { id: "已撤销", label: "已撤销" }] },
      { name: "remark", label: "备注", type: "textarea" }
    ]
  },
  {
    key: "penalties",
    title: "处罚处理",
    icon: AlertTriangle,
    accent: "text-amber",
    columns: [
      { key: "penalty_id", label: "ID" },
      { key: "source_plate_number", label: "来源车牌" },
      { key: "trigger_type", label: "触发" },
      { key: "penalty_description", label: "处罚" },
      { key: "start_date", label: "开始" },
      { key: "end_date", label: "结束" },
      { key: "status", label: "状态" }
    ],
    fields: [
      { name: "violation_id", label: "违规ID", type: "number" },
      { name: "source_vehicle_id", label: "来源车辆", type: "select", optionKey: "vehicles" },
      { name: "period_id", label: "记分周期", type: "select", optionKey: "periods" },
      { name: "trigger_type", label: "触发类型", type: "select", options: [{ id: "单次违规", label: "单次违规" }, { id: "累计扣分", label: "累计扣分" }, { id: "恶性行为", label: "恶性行为" }, { id: "人工处理", label: "人工处理" }] },
      { name: "penalty_type", label: "处罚类型", type: "select", options: ["扣分", "暂停入校", "通报单位", "谈话提醒", "预约黑名单", "暂停因私预约", "取消房屋预约", "永久禁止", "全校通报"].map((x) => ({ id: x, label: x })) },
      { name: "points_deducted", label: "扣分", type: "number" },
      { name: "suspension_days", label: "暂停天数", type: "number" },
      { name: "start_date", label: "开始日期", type: "date" },
      { name: "end_date", label: "结束日期", type: "date" },
      { name: "target_vehicle_id", label: "目标车辆", type: "select", optionKey: "vehicles" },
      { name: "target_dept_id", label: "目标单位", type: "select", optionKey: "departments" },
      { name: "target_person_id", label: "目标个人", type: "select", optionKey: "registrants" },
      { name: "target_house_id", label: "目标房屋", type: "select", optionKey: "houses" },
      { name: "status", label: "状态", type: "select", options: [{ id: "待执行", label: "待执行" }, { id: "执行中", label: "执行中" }, { id: "已完成", label: "已完成" }, { id: "已撤销", label: "已撤销" }] }
    ]
  },
  {
    key: "appeals",
    title: "申诉审批",
    icon: FilePenLine,
    accent: "text-cyan",
    columns: [
      { key: "appeal_id", label: "ID" },
      { key: "violation_remark", label: "违规" },
      { key: "applicant_name", label: "申请人" },
      { key: "reason", label: "理由" },
      { key: "status", label: "状态" },
      { key: "handler_opinion", label: "处理意见" }
    ],
    fields: [
      { name: "violation_id", label: "违规ID", type: "number" },
      { name: "applicant_id", label: "申请人", type: "select", optionKey: "registrants" },
      { name: "reason", label: "申诉理由", type: "textarea" },
      { name: "evidence_path", label: "附件路径" },
      { name: "status", label: "状态", type: "select", options: [{ id: "待处理", label: "待处理" }, { id: "已通过", label: "已通过" }, { id: "已驳回", label: "已驳回" }, { id: "已撤回", label: "已撤回" }] },
      { name: "handler_id", label: "处理人", type: "select", optionKey: "users" },
      { name: "handler_opinion", label: "处理意见", type: "textarea" }
    ]
  },
  {
    key: "points-additions",
    title: "加分申请",
    icon: Gauge,
    accent: "text-pine",
    columns: [
      { key: "addition_id", label: "ID" },
      { key: "plate_number", label: "车辆" },
      { key: "applicant_name", label: "申请人" },
      { key: "addition_points", label: "加分" },
      { key: "status", label: "状态" },
      { key: "approver_opinion", label: "审批意见" }
    ],
    fields: [
      { name: "period_id", label: "记分周期", type: "select", optionKey: "periods" },
      { name: "vehicle_id", label: "车辆", type: "select", optionKey: "vehicles" },
      { name: "applicant_id", label: "申请人", type: "select", optionKey: "registrants" },
      { name: "addition_points", label: "加分分值", type: "number" },
      { name: "proof_path", label: "证明材料路径" },
      { name: "status", label: "状态", type: "select", options: [{ id: "待审批", label: "待审批" }, { id: "已通过", label: "已通过" }, { id: "已驳回", label: "已驳回" }, { id: "已撤回", label: "已撤回" }] },
      { name: "approver_id", label: "审批人", type: "select", optionKey: "users" },
      { name: "approver_opinion", label: "审批意见", type: "textarea" }
    ]
  },
  {
    key: "scoring-periods",
    title: "记分周期",
    icon: Gauge,
    accent: "text-cyan",
    columns: [
      { key: "period_id", label: "ID" },
      { key: "plate_number", label: "车辆" },
      { key: "year", label: "年份" },
      { key: "deducted_points_total", label: "累计扣分" },
      { key: "added_points_total", label: "累计加分" },
      { key: "has_danger_violation", label: "危险违规" },
      { key: "remaining_points", label: "剩余分" }
    ],
    fields: [
      { name: "vehicle_id", label: "车辆", type: "select", optionKey: "vehicles" },
      { name: "year", label: "年份", type: "number" },
      { name: "initial_points", label: "初始分", type: "number" },
      { name: "deducted_points_total", label: "累计扣分", type: "number" },
      { name: "added_points_total", label: "累计加分", type: "number" },
      { name: "add_count", label: "加分次数", type: "number" },
      { name: "has_danger_violation", label: "危险违规", type: "select", options: [{ id: 1, label: "是" }, { id: 0, label: "否" }] },
      { name: "is_active", label: "活跃周期", type: "select", options: [{ id: 1, label: "是" }, { id: 0, label: "否" }] }
    ]
  },
  {
    key: "blacklists",
    title: "黑名单",
    icon: ListFilter,
    accent: "text-berry",
    columns: [
      { key: "blacklist_id", label: "ID" },
      { key: "plate_number", label: "车辆" },
      { key: "blacklist_type", label: "类型" },
      { key: "reason", label: "原因" },
      { key: "penalty_id", label: "处罚记录号" },
      { key: "end_date", label: "截止" },
      { key: "is_active", label: "有效" }
    ],
    fields: [
      { name: "vehicle_id", label: "车辆", type: "select", optionKey: "vehicles" },
      { name: "blacklist_type", label: "类型", type: "select", options: [{ id: "临时", label: "临时" }, { id: "永久", label: "永久" }] },
      { name: "reason", label: "原因", type: "textarea" },
      { name: "source_type", label: "来源类型" },
      { name: "penalty_id", label: "处罚ID", type: "number" },
      { name: "start_date", label: "开始日期", type: "date" },
      { name: "end_date", label: "结束日期", type: "date" },
      { name: "is_active", label: "是否有效", type: "select", options: [{ id: 1, label: "有效" }, { id: 0, label: "无效" }] }
    ]
  },
  {
    key: "notifications",
    title: "通知日志",
    icon: Bell,
    accent: "text-pine",
    columns: [
      { key: "notification_id", label: "ID" },
      { key: "notification_type", label: "类型" },
      { key: "recipient", label: "接收方" },
      { key: "recipient_type", label: "对象" },
      { key: "send_status", label: "状态" },
      { key: "content", label: "内容" }
    ],
    fields: [
      { name: "vehicle_id", label: "车辆", type: "select", optionKey: "vehicles" },
      { name: "violation_id", label: "违规ID", type: "number" },
      { name: "penalty_id", label: "处罚ID", type: "number" },
      { name: "notification_type", label: "通知类型" },
      { name: "recipient", label: "接收方" },
      { name: "recipient_type", label: "接收方类型" },
      { name: "content", label: "内容", type: "textarea" },
      { name: "sent_time", label: "发送时间", type: "datetime-local" },
      { name: "send_status", label: "状态", type: "select", options: [{ id: "待发送", label: "待发送" }, { id: "已发送", label: "已发送" }, { id: "发送失败", label: "发送失败" }] }
    ]
  },
  {
    key: "ai-query-logs",
    title: "智能查询",
    icon: Bot,
    accent: "text-amber",
    columns: [
      { key: "query_id", label: "ID" },
      { key: "requester_user_id", label: "用户" },
      { key: "natural_language_question", label: "问题" },
      { key: "execution_status", label: "状态" },
      { key: "rows_returned", label: "行数" },
      { key: "created_at", label: "创建时间" }
    ],
    fields: [
      { name: "requester_user_id", label: "请求用户", type: "select", optionKey: "users" },
      { name: "natural_language_question", label: "自然语言问题", type: "textarea" },
      { name: "generated_sql", label: "生成SQL", type: "textarea" },
      { name: "is_readonly", label: "只读", type: "select", options: [{ id: 1, label: "是" }, { id: 0, label: "否" }] },
      { name: "execution_status", label: "状态", type: "select", options: [{ id: "待审核", label: "待审核" }, { id: "已执行", label: "已执行" }, { id: "已拒绝", label: "已拒绝" }, { id: "执行失败", label: "执行失败" }] },
      { name: "error_message", label: "错误信息", type: "textarea" }
    ]
  }
];

const statLabels: Record<string, string> = {
  vehicle_count: "车辆总数",
  normal_vehicle_count: "正常车辆",
  violation_count: "违规记录",
  active_penalty_count: "执行中处罚",
  pending_appointment_count: "待审预约",
  pending_appeal_count: "待处理申诉",
  active_blacklist_count: "有效黑名单",
  ai_query_count: "智能查询"
};

const ownerStatKeys = ["vehicle_count", "normal_vehicle_count", "violation_count", "active_penalty_count", "pending_appointment_count", "pending_appeal_count"];

const simpleTableColumnLabels: Record<string, string> = {
  plate_number: "车牌号",
  violation_type: "违规类型",
  violation_level: "违规等级",
  points_deducted: "扣分",
  location: "地点",
  status: "状态",
  penalty_type: "处罚类型",
  trigger_type: "触发类型",
  start_date: "开始日期",
  end_date: "结束日期",
  query_id: "查询编号",
  requester_user_id: "请求用户",
  natural_language_question: "自然语言问题",
  generated_sql: "生成 SQL",
  execution_status: "执行状态",
  rows_returned: "返回行数",
  created_at: "创建时间"
};

function simpleTableColumnClass(column: string) {
  if (column === "location") return "min-w-[180px] w-[32%]";
  if (column.includes("date") || column.includes("time") || column === "created_at") return "min-w-[120px]";
  if (column === "plate_number") return "min-w-[96px]";
  return "min-w-[88px]";
}

function display(value: Row[string]) {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "boolean") return value ? "是" : "否";
  return String(value).replace("T", " ");
}

function inputValue(value: Row[string] | undefined, type?: Field["type"]) {
  if (value === null || value === undefined) return "";
  const text = String(value);
  if (type === "datetime-local") return text.slice(0, 16);
  if (type === "date") return text.slice(0, 10);
  return text;
}

function payloadFromForm(form: HTMLFormElement, fields: Field[]) {
  const data = new FormData(form);
  const payload: Record<string, string | number | null> = {};
  for (const field of fields) {
    const value = String(data.get(field.name) ?? "").trim();
    if (value === "") {
      payload[field.name] = null;
    } else if (field.type === "number" || field.optionKey || field.name.endsWith("_id") || field.name === "is_active" || field.name === "is_readonly") {
      payload[field.name] = Number(value);
    } else {
      payload[field.name] = value;
    }
  }
  return payload;
}

function Badge({ value }: { value: Row[string] }) {
  const text = display(value);
  const className = text.includes("正常") || text.includes("已通过") || text.includes("有效") || text === "是"
    ? "border-emerald-200 bg-emerald-50 text-emerald-700"
    : text.includes("暂停") || text.includes("待") || text.includes("执行")
      ? "border-amber-200 bg-amber-50 text-amber-700"
      : text.includes("禁止") || text.includes("驳回") || text.includes("黑名单")
        ? "border-rose-200 bg-rose-50 text-rose-700"
        : "border-slate-200 bg-slate-50 text-slate-600";
  return <span className={`inline-flex min-h-7 items-center rounded-md border px-2 text-sm ${className}`}>{text}</span>;
}

function FieldInput({ field, row, options }: { field: Field; row?: Row | null; options: OptionsPayload }) {
  const fieldOptions = field.options ?? (field.optionKey ? options[field.optionKey] : undefined) ?? [];
  const base = "min-h-10 w-full rounded-md border border-line bg-white px-3 text-sm outline-none transition focus:border-cyan focus:ring-4 focus:ring-cyan/10";
  const value = inputValue(row?.[field.name], field.type);

  if (field.type === "textarea") {
    return <textarea name={field.name} defaultValue={value} placeholder={field.placeholder} className={`${base} min-h-24 py-2`} />;
  }
  if (field.type === "select") {
    return (
      <select name={field.name} defaultValue={value} className={base}>
        <option value="">不填写</option>
        {fieldOptions.map((option) => (
          <option key={String(option.id)} value={String(option.id)}>
            {option.label}
          </option>
        ))}
      </select>
    );
  }
  return <input name={field.name} type={field.type ?? "text"} defaultValue={value} placeholder={field.placeholder} className={base} />;
}

function RecordDialog({
  config,
  row,
  options,
  open,
  onOpenChange,
  onSubmit
}: {
  config: ResourceConfig;
  row: Row | null;
  options: OptionsPayload;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (payload: Record<string, string | number | null>) => Promise<void>;
}) {
  const title = row ? `编辑${config.title}` : `新增${config.title}`;
  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onSubmit(payloadFromForm(event.currentTarget, config.fields));
  }
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-ink/35" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 max-h-[88vh] w-[min(780px,calc(100vw-32px))] -translate-x-1/2 -translate-y-1/2 overflow-hidden rounded-lg border border-line bg-white shadow-soft">
          <div className="flex items-center justify-between border-b border-line px-5 py-4">
            <Dialog.Title className="text-lg font-semibold">{title}</Dialog.Title>
            <Dialog.Close className="rounded-md p-2 text-slate-500 hover:bg-slate-100" aria-label="关闭">
              <X size={18} />
            </Dialog.Close>
          </div>
          <form onSubmit={handleSubmit} className="max-h-[calc(88vh-74px)] overflow-y-auto p-5">
            <div className="grid gap-4 md:grid-cols-2">
              {config.fields.map((field) => (
                <label key={field.name} className={field.type === "textarea" ? "md:col-span-2" : ""}>
                  <span className="mb-1.5 block text-sm font-medium text-slate-700">{field.label}</span>
                  <FieldInput field={field} row={row} options={options} />
                </label>
              ))}
            </div>
            <div className="mt-5 flex justify-end gap-3 border-t border-line pt-4">
              <Dialog.Close className="inline-flex min-h-10 items-center gap-2 rounded-md border border-line px-4 text-sm hover:bg-slate-50">
                <X size={16} /> 取消
              </Dialog.Close>
              <button className="inline-flex min-h-10 items-center gap-2 rounded-md bg-ink px-4 text-sm font-medium text-white hover:bg-slate-700">
                <Check size={16} /> 保存
              </button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

export default function Page() {
  const [activeKey, setActiveKey] = useState("dashboard");
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [dashboard, setDashboard] = useState<DashboardPayload | null>(null);
  const [options, setOptions] = useState<OptionsPayload>({});
  const [table, setTable] = useState<TablePayload>({ items: [], total: 0, limit: 50, offset: 0 });
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingRow, setEditingRow] = useState<Row | null>(null);
  const [deleteRow, setDeleteRow] = useState<Row | null>(null);
  const [toast, setToast] = useState({ open: false, title: "", description: "" });
  const [health, setHealth] = useState<string>("检查中");
  const [gatePlate, setGatePlate] = useState("");
  const [gateResult, setGateResult] = useState<Row | null>(null);
  const [aiResult, setAiResult] = useState<Row[] | null>(null);

  const visibleConfigs = useMemo(() => {
    if (!currentUser) return [];
    if (isAdminUser(currentUser)) return resourceConfigs;
    return resourceConfigs.filter((config) => ownerResourceKeys.has(config.key));
  }, [currentUser]);
  const activeConfig = useMemo(() => visibleConfigs.find((config) => config.key === activeKey), [activeKey, visibleConfigs]);
  const canManage = isAdminUser(currentUser);
  const canCreate = canManage || (!canManage && ["appointments", "appeals", "points-additions"].includes(activeKey));
  const showDashboardTools = activeKey === "dashboard";
  const showAiDemo = canManage && (activeKey === "dashboard" || activeKey === "ai-query-logs");

  function showToast(title: string, description = "") {
    setToast({ open: true, title, description });
  }

  async function refreshDashboard() {
    const data = await apiGet<DashboardPayload>("/dashboard");
    setDashboard(data);
  }

  async function refreshTable(config = activeConfig) {
    if (!config) return;
    setLoading(true);
    try {
      const params = new URLSearchParams({ limit: "50", offset: "0" });
      if (search.trim()) params.set("search", search.trim());
      const data = await apiGet<TablePayload>(`/${config.key}?${params.toString()}`);
      setTable(data);
    } finally {
      setLoading(false);
    }
  }

  async function bootstrap() {
    const stored = window.localStorage.getItem("currentUser");
    if (!stored) return;
    const user = JSON.parse(stored) as CurrentUser;
    setCurrentUser(user);
    try {
      const healthData = await apiGet<{ database: string; server_time: string }>("/health");
      setHealth(`${healthData.database} 已连接`);
      const opts = await apiGet<OptionsPayload>("/options");
      setOptions(opts);
      await refreshDashboard();
    } catch (error) {
      setHealth("数据库未连接");
      showToast("连接失败", error instanceof Error ? error.message : "请检查 Flask 后端和 SQL Server 配置");
    }
  }

  useEffect(() => {
    void bootstrap();
  }, []);

  useEffect(() => {
    if (activeConfig) void refreshTable(activeConfig);
  }, [activeKey, currentUser]);

  useEffect(() => {
    if (currentUser && activeKey !== "dashboard" && !visibleConfigs.some((config) => config.key === activeKey)) {
      setActiveKey("dashboard");
    }
  }, [currentUser, activeKey, visibleConfigs]);

  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const payload = {
      username: String(form.get("username") ?? ""),
      password: String(form.get("password") ?? "")
    };
    const user = await apiSend<CurrentUser>("/auth/login", "POST", payload);
    window.localStorage.setItem("currentUser", JSON.stringify(user));
    window.localStorage.setItem("currentUserId", String(user.user_id));
    setCurrentUser(user);
    showToast("登录成功", `${user.real_name}，欢迎回来`);
    await bootstrap();
  }

  function logout() {
    window.localStorage.removeItem("currentUser");
    window.localStorage.removeItem("currentUserId");
    setCurrentUser(null);
    setDashboard(null);
    setTable({ items: [], total: 0, limit: 50, offset: 0 });
    setActiveKey("dashboard");
  }

  async function saveRecord(payload: Record<string, string | number | null>) {
    if (!canManage && editingRow) {
      showToast("权限不足", "普通车主仅支持查看自己的相关信息");
      return;
    }
    if (!canManage && !canCreate) {
      showToast("权限不足", "当前页面不支持普通车主新增");
      return;
    }
    if (!activeConfig) return;
    if (editingRow) {
      await apiSend(`/${activeConfig.key}/${editingRow[activeConfig.columns[0].key]}`, "PUT", payload);
      showToast("更新成功", `${activeConfig.title}记录已保存`);
    } else {
      await apiSend(`/${activeConfig.key}`, "POST", payload);
      showToast("新增成功", `${activeConfig.title}记录已创建`);
    }
    setDialogOpen(false);
    setEditingRow(null);
    await refreshTable();
    await refreshDashboard();
  }

  async function confirmDelete() {
    if (!canManage) {
      showToast("权限不足", "普通车主仅支持查看自己的相关信息");
      return;
    }
    if (!activeConfig || !deleteRow) return;
    await apiSend(`/${activeConfig.key}/${deleteRow[activeConfig.columns[0].key]}`, "DELETE");
    showToast("删除成功", `${activeConfig.title}记录已删除`);
    setDeleteRow(null);
    await refreshTable();
    await refreshDashboard();
  }

  async function runGateCheck() {
    if (!canManage) {
      showToast("权限不足", "门禁核验仅管理员可用");
      return;
    }
    if (!gatePlate.trim()) {
      showToast("请输入车牌号");
      return;
    }
    const data = await apiGet<Row>(`/gate-check?plate=${encodeURIComponent(gatePlate.trim())}`);
    setGateResult(data);
    showToast("门禁核验完成", String(data.reason ?? ""));
  }

  async function runAiQuery(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canManage) {
      showToast("权限不足", "查询智能体审计仅管理员可用");
      return;
    }
    const form = new FormData(event.currentTarget);
    const payload = {
      requester_user_id: Number(form.get("requester_user_id")),
      natural_language_question: String(form.get("natural_language_question") ?? ""),
      generated_sql: String(form.get("generated_sql") ?? "")
    };
    const data = await apiSend<{ rows: Row[]; query_id: number }>("/ai-query/execute-readonly", "POST", payload);
    setAiResult(data.rows);
    showToast("智能查询完成", `已返回 ${data.rows.length} 行，日志编号 ${data.query_id}`);
    if (activeKey === "ai-query-logs") await refreshTable();
  }

  async function reviewLearning(additionId: Row[string], status: "已通过" | "已驳回") {
    await apiSend(`/points-additions/${additionId}/review`, "POST", {
      status,
      approver_opinion: status === "已通过" ? "学习材料审核通过" : "学习材料不符合要求"
    });
    showToast("审批完成", `学习申请已${status}`);
    await refreshTable();
    await refreshDashboard();
  }

  async function annualReset() {
    const year = new Date().getFullYear();
    const data = await apiSend<{ year: number; created_periods: number }>("/scoring-periods/annual-reset", "POST", { year });
    showToast("年度重置完成", `${data.year} 年新增 ${data.created_periods} 个记分周期`);
    await refreshDashboard();
    if (activeConfig) await refreshTable();
  }

  if (!currentUser) {
    return (
      <Toast.Provider swipeDirection="right">
        <main className="grid min-h-screen place-items-center bg-mist px-4">
          <section className="w-full max-w-md rounded-lg border border-line bg-white p-6 shadow-soft">
            <div className="mb-6 flex items-center gap-3">
              <div className="grid h-11 w-11 place-items-center rounded-lg bg-ink text-white">
                <Database size={22} />
              </div>
              <div>
                <h1 className="text-xl font-semibold">校园机动车管理</h1>
                <p className="text-sm text-slate-500">登录后进入对应权限视图</p>
              </div>
            </div>
            <form onSubmit={handleLogin} className="space-y-4">
              <label className="block">
                <span className="mb-1.5 block text-sm font-medium text-slate-700">用户名</span>
                <input name="username" placeholder="admin 或 zhangming" className="min-h-11 w-full rounded-md border border-line px-3 text-sm outline-none focus:border-cyan focus:ring-4 focus:ring-cyan/10" />
              </label>
              <label className="block">
                <span className="mb-1.5 block text-sm font-medium text-slate-700">密码</span>
                <input name="password" type="password" placeholder="演示密码 123456" className="min-h-11 w-full rounded-md border border-line px-3 text-sm outline-none focus:border-cyan focus:ring-4 focus:ring-cyan/10" />
              </label>
              <button className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-md bg-ink px-4 text-sm font-medium text-white hover:bg-slate-700">
                <UserRound size={17} /> 登录
              </button>
            </form>
            <div className="mt-4 rounded-lg border border-line bg-slate-50 p-3 text-sm text-slate-600">
              <div>管理员示例：`admin` / `123456`</div>
              <div className="mt-1">车主示例：`zhangming` / `123456`</div>
            </div>
          </section>
        </main>
        <Toast.Root open={toast.open} onOpenChange={(open) => setToast((current) => ({ ...current, open }))} className="rounded-lg border border-line bg-white p-4 shadow-soft">
          <Toast.Title className="font-semibold">{toast.title}</Toast.Title>
          {toast.description && <Toast.Description className="mt-1 text-sm text-slate-600">{toast.description}</Toast.Description>}
        </Toast.Root>
        <Toast.Viewport className="fixed bottom-5 right-5 z-[80] w-[min(380px,calc(100vw-32px))]" />
      </Toast.Provider>
    );
  }

  return (
    <Toast.Provider swipeDirection="right">
      <main className="min-h-screen bg-mist">
        <div className="flex min-h-screen">
          <aside className="hidden w-72 shrink-0 border-r border-line bg-white px-4 py-5 lg:block">
            <div className="mb-6 flex items-center gap-3 px-2">
              <div className="grid h-10 w-10 place-items-center rounded-lg bg-ink text-white">
                <Database size={21} />
              </div>
              <div>
                <h1 className="text-base font-semibold">校园机动车管理</h1>
                <p className="text-sm text-slate-500">{health}</p>
                <p className="mt-1 text-xs text-slate-500">{currentUser.real_name} / {currentUser.role}</p>
              </div>
            </div>
            <nav className="space-y-1">
              <button
                onClick={() => setActiveKey("dashboard")}
                className={`flex min-h-11 w-full items-center gap-3 rounded-md px-3 text-left text-sm ${activeKey === "dashboard" ? "bg-ink text-white" : "text-slate-700 hover:bg-slate-100"}`}
              >
                <LayoutDashboard size={18} /> 总览
              </button>
              {visibleConfigs.map((config) => {
                const Icon = config.icon;
                return (
                  <button
                    key={config.key}
                    onClick={() => setActiveKey(config.key)}
                    className={`flex min-h-11 w-full items-center gap-3 rounded-md px-3 text-left text-sm ${activeKey === config.key ? "bg-ink text-white" : "text-slate-700 hover:bg-slate-100"}`}
                  >
                    <Icon size={18} /> {config.title}
                  </button>
                );
              })}
            </nav>
          </aside>

          <section className="min-w-0 flex-1">
            <header className="border-b border-line bg-white px-5 py-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-sm text-slate-500">{canManage ? "保卫处交通管理后台" : "车主个人服务台"}</p>
                  <h2 className="text-2xl font-semibold">{activeConfig?.title ?? "业务总览"}</h2>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button
                    onClick={() => (activeConfig ? refreshTable() : refreshDashboard())}
                    className="inline-flex min-h-10 items-center gap-2 rounded-md border border-line bg-white px-4 text-sm hover:bg-slate-50"
                  >
                    <RefreshCcw size={16} /> 刷新
                  </button>
                  {canManage && (
                    <button onClick={annualReset} className="inline-flex min-h-10 items-center gap-2 rounded-md border border-line bg-white px-4 text-sm hover:bg-slate-50">
                      <Gauge size={16} /> 年度重置
                    </button>
                  )}
                  <button onClick={logout} className="inline-flex min-h-10 items-center gap-2 rounded-md border border-line bg-white px-4 text-sm hover:bg-slate-50">
                    <LogOut size={16} /> 退出
                  </button>
                </div>
              </div>
            </header>

            <div className="space-y-5 p-5">
              {showDashboardTools && <section className={`grid gap-4 ${canManage ? "xl:grid-cols-[1fr_420px]" : ""}`}>
                <div className="rounded-lg border border-line bg-white p-4 shadow-sm">
                  <div className="mb-4 flex items-center gap-2">
                    <Gauge className="text-pine" size={20} />
                    <h3 className="text-base font-semibold">运行概览</h3>
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                    {Object.entries(statLabels).filter(([key]) => canManage || ownerStatKeys.includes(key)).map(([key, label]) => (
                      <div key={key} className="rounded-lg border border-line bg-slate-50 p-3">
                        <p className="text-sm text-slate-500">{label}</p>
                        <p className="mt-2 text-2xl font-semibold">{dashboard?.stats?.[key] ?? "—"}</p>
                      </div>
                    ))}
                  </div>
                </div>

                {canManage && <div className="rounded-lg border border-line bg-white p-4 shadow-sm">
                  <div className="mb-4 flex items-center gap-2">
                    <Search className="text-cyan" size={20} />
                    <h3 className="text-base font-semibold">门禁核验</h3>
                  </div>
                  <div className="flex gap-2">
                    <input
                      value={gatePlate}
                      onChange={(event) => setGatePlate(event.target.value)}
                      placeholder="输入车牌号"
                      className="min-h-10 flex-1 rounded-md border border-line px-3 text-sm outline-none focus:border-cyan focus:ring-4 focus:ring-cyan/10"
                    />
                    <button onClick={runGateCheck} className="inline-flex min-h-10 items-center gap-2 rounded-md bg-cyan px-4 text-sm font-medium text-white hover:bg-cyan/90">
                      <Search size={16} /> 核验
                    </button>
                  </div>
                  {gateResult && (
                    <div className={`mt-3 rounded-lg border p-3 text-sm ${gateResult.can_enter ? "border-emerald-200 bg-emerald-50 text-emerald-800" : "border-rose-200 bg-rose-50 text-rose-800"}`}>
                      <div className="font-medium">{gateResult.can_enter ? "允许入校" : "禁止入校"}</div>
                      <div className="mt-1">{String(gateResult.reason ?? "")}</div>
                    </div>
                  )}
                </div>}
              </section>}

              {activeKey === "dashboard" ? (
                <section className="grid gap-4 xl:grid-cols-2">
                  <div className="rounded-lg border border-line bg-white p-4 shadow-sm">
                    <h3 className="mb-3 text-base font-semibold">最近违规</h3>
                    <SimpleTable rows={dashboard?.latest_violations ?? []} columns={["plate_number", "violation_type", "violation_level", "points_deducted", "location", "status"]} />
                  </div>
                  <div className="rounded-lg border border-line bg-white p-4 shadow-sm">
                    <h3 className="mb-3 text-base font-semibold">执行中处罚</h3>
                    <SimpleTable rows={dashboard?.active_penalties ?? []} columns={["plate_number", "penalty_type", "trigger_type", "status", "start_date", "end_date"]} />
                  </div>
                </section>
              ) : (
                activeConfig && activeConfig.key !== "ai-query-logs" && (
                  <section className="rounded-lg border border-line bg-white shadow-sm">
                    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line p-4">
                      <div className="flex items-center gap-2">
                        <activeConfig.icon className={activeConfig.accent} size={20} />
                        <div>
                          <h3 className="text-base font-semibold">{activeConfig.title}</h3>
                          <p className="text-sm text-slate-500">共 {table.total} 条记录</p>
                        </div>
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        <div className="relative">
                          <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
                          <input
                            value={search}
                            onChange={(event) => setSearch(event.target.value)}
                            onKeyDown={(event) => {
                              if (event.key === "Enter") void refreshTable();
                            }}
                            placeholder="搜索"
                            className="min-h-10 w-56 rounded-md border border-line pl-9 pr-3 text-sm outline-none focus:border-cyan focus:ring-4 focus:ring-cyan/10"
                          />
                        </div>
                        <button onClick={() => refreshTable()} className="inline-flex min-h-10 items-center gap-2 rounded-md border border-line px-3 text-sm hover:bg-slate-50">
                          <Search size={16} /> 查询
                        </button>
                        {canCreate && <button
                          onClick={() => {
                            setEditingRow(null);
                            setDialogOpen(true);
                          }}
                          className="inline-flex min-h-10 items-center gap-2 rounded-md bg-ink px-4 text-sm font-medium text-white hover:bg-slate-700"
                        >
                          <Plus size={16} /> 新增
                        </button>}
                      </div>
                    </div>
                    <div className="overflow-x-auto">
                      <table className={`w-full border-collapse text-sm ${activeConfig.key === "violations" ? "min-w-[1280px]" : "min-w-[860px]"}`}>
                        <thead>
                          <tr className="border-b border-line bg-slate-50 text-left text-slate-600">
                            {activeConfig.columns.map((column) => (
                              <th key={column.key} className="px-4 py-3 font-medium">{column.label}</th>
                            ))}
                            {(canManage || activeConfig.key === "points-additions") && <th className="px-4 py-3 text-right font-medium">操作</th>}
                          </tr>
                        </thead>
                        <tbody>
                          {loading ? (
                            <tr>
                              <td colSpan={activeConfig.columns.length + ((canManage || activeConfig.key === "points-additions") ? 1 : 0)} className="px-4 py-12 text-center text-slate-500">
                                <Loader2 className="mx-auto mb-2 animate-spin" size={24} /> 正在加载
                              </td>
                            </tr>
                          ) : table.items.length === 0 ? (
                            <tr>
                              <td colSpan={activeConfig.columns.length + ((canManage || activeConfig.key === "points-additions") ? 1 : 0)} className="px-4 py-12 text-center text-slate-500">暂无数据</td>
                            </tr>
                          ) : (
                            table.items.map((row) => (
                              <tr key={String(row[activeConfig.columns[0].key])} className="border-b border-line last:border-0 hover:bg-slate-50">
                                {activeConfig.columns.map((column) => (
                                  <td key={column.key} className="max-w-64 px-4 py-3 align-middle">
                                    {column.key.includes("status") || column.key === "is_active" ? <Badge value={row[column.key]} /> : <span className="line-clamp-2">{display(row[column.key])}</span>}
                                  </td>
                                ))}
                                {(canManage || activeConfig.key === "points-additions") && <td className="px-4 py-3">
                                  <div className="flex justify-end gap-2">
                                    {canManage && <button
                                      onClick={() => {
                                        setEditingRow(row);
                                        setDialogOpen(true);
                                      }}
                                      className="inline-flex min-h-9 items-center gap-1 rounded-md border border-line px-3 text-sm hover:bg-white"
                                    >
                                      <SquarePen size={15} /> 编辑
                                    </button>}
                                    {canManage && <button
                                      onClick={() => setDeleteRow(row)}
                                      className="inline-flex min-h-9 items-center gap-1 rounded-md border border-rose-200 px-3 text-sm text-rose-700 hover:bg-rose-50"
                                    >
                                      <Trash2 size={15} /> 删除
                                    </button>}
                                    {canManage && activeConfig.key === "points-additions" && row.status === "待审批" && (
                                      <>
                                        <button onClick={() => reviewLearning(row.addition_id, "已通过")} className="inline-flex min-h-9 items-center gap-1 rounded-md border border-emerald-200 px-3 text-sm text-emerald-700 hover:bg-emerald-50">
                                          <Check size={15} /> 通过
                                        </button>
                                        <button onClick={() => reviewLearning(row.addition_id, "已驳回")} className="inline-flex min-h-9 items-center gap-1 rounded-md border border-rose-200 px-3 text-sm text-rose-700 hover:bg-rose-50">
                                          <X size={15} /> 驳回
                                        </button>
                                      </>
                                    )}
                                  </div>
                                </td>}
                              </tr>
                            ))
                          )}
                        </tbody>
                      </table>
                    </div>
                  </section>
                )
              )}

              {showAiDemo && <section className="rounded-lg border border-line bg-white p-4 shadow-sm">
                <div className="mb-4 flex items-center gap-2">
                  <Bot className="text-amber" size={20} />
                  <h3 className="text-base font-semibold">查询智能体审计演示</h3>
                </div>
                <form onSubmit={runAiQuery} className="grid gap-3 xl:grid-cols-[220px_1fr_1.4fr_auto]">
                  <select name="requester_user_id" className="min-h-10 rounded-md border border-line px-3 text-sm outline-none focus:border-cyan focus:ring-4 focus:ring-cyan/10">
                    {(options.users ?? []).map((user) => <option key={String(user.id)} value={String(user.id)}>{user.label}</option>)}
                  </select>
                  <input name="natural_language_question" placeholder="自然语言问题" className="min-h-10 rounded-md border border-line px-3 text-sm outline-none focus:border-cyan focus:ring-4 focus:ring-cyan/10" />
                  <input name="generated_sql" placeholder="SELECT plate_number, register_status FROM dbo.t_vehicle" className="min-h-10 rounded-md border border-line px-3 text-sm outline-none focus:border-cyan focus:ring-4 focus:ring-cyan/10" />
                  <button className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md bg-amber px-4 text-sm font-medium text-white hover:bg-amber/90">
                    <Bot size={16} /> 执行
                  </button>
                </form>
                {aiResult && (
                  <div className="mt-4 overflow-x-auto rounded-lg border border-line">
                    <SimpleTable rows={aiResult} columns={Object.keys(aiResult[0] ?? { result: "" })} />
                  </div>
                )}
              </section>}
            </div>
          </section>
        </div>

        {activeConfig && (
          <RecordDialog
            config={activeConfig}
            row={editingRow}
            options={options}
            open={dialogOpen}
            onOpenChange={setDialogOpen}
            onSubmit={saveRecord}
          />
        )}

        <Dialog.Root open={!!deleteRow} onOpenChange={(open) => !open && setDeleteRow(null)}>
          <Dialog.Portal>
            <Dialog.Overlay className="fixed inset-0 z-40 bg-ink/35" />
            <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[min(420px,calc(100vw-32px))] -translate-x-1/2 -translate-y-1/2 rounded-lg border border-line bg-white p-5 shadow-soft">
              <Dialog.Title className="text-lg font-semibold">确认删除</Dialog.Title>
              <p className="mt-2 text-sm text-slate-600">删除后将无法在当前页面恢复，且可能受到外键约束限制。</p>
              <div className="mt-5 flex justify-end gap-3">
                <Dialog.Close className="inline-flex min-h-10 items-center gap-2 rounded-md border border-line px-4 text-sm hover:bg-slate-50">
                  <X size={16} /> 取消
                </Dialog.Close>
                <button onClick={confirmDelete} className="inline-flex min-h-10 items-center gap-2 rounded-md bg-rose-600 px-4 text-sm font-medium text-white hover:bg-rose-700">
                  <Trash2 size={16} /> 删除
                </button>
              </div>
            </Dialog.Content>
          </Dialog.Portal>
        </Dialog.Root>
      </main>

      <Toast.Root open={toast.open} onOpenChange={(open) => setToast((current) => ({ ...current, open }))} className="rounded-lg border border-line bg-white p-4 shadow-soft">
        <Toast.Title className="font-semibold">{toast.title}</Toast.Title>
        {toast.description && <Toast.Description className="mt-1 text-sm text-slate-600">{toast.description}</Toast.Description>}
      </Toast.Root>
      <Toast.Viewport className="fixed bottom-5 right-5 z-[80] w-[min(380px,calc(100vw-32px))]" />
    </Toast.Provider>
  );
}

function SimpleTable({ rows, columns }: { rows: Row[]; columns: string[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px] border-collapse text-sm">
        <thead>
          <tr className="border-b border-line bg-slate-50 text-left text-slate-600">
            {columns.map((column) => (
              <th key={column} className={`px-3 py-2 font-medium ${simpleTableColumnClass(column)}`}>{simpleTableColumnLabels[column] ?? column}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={columns.length || 1} className="px-3 py-8 text-center text-slate-500">暂无数据</td>
            </tr>
          ) : (
            rows.map((row, index) => (
              <tr key={index} className="border-b border-line last:border-0">
                {columns.map((column) => (
                  <td key={column} className={`px-3 py-2 align-top ${simpleTableColumnClass(column)}`}>
                    <span className={column === "location" ? "line-clamp-3 break-words" : "line-clamp-2 break-words"}>{display(row[column])}</span>
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
