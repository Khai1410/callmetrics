import { useEffect, useRef, useState } from "react";
import { CriteriaApi } from "../api/client";
import type { CriteriaSet, CriteriaSetWithCriteria, Criterion } from "../api/types";
import { IconEdit, IconPlus, IconTrash } from "../components/Icons";

type ContextMenuState = { criterionId: string; x: number; y: number };

type CriterionFormState = {
  stt: number;
  name: string;
  description: string;
  weight: string;
  include_in_total: boolean;
  selection_type: "single" | "multiple";
  score_options: string;
  check_type: "manual" | "keyword";
  check_config: string;
};

const emptyForm: CriterionFormState = {
  stt: 1,
  name: "",
  description: "",
  weight: "",
  include_in_total: true,
  selection_type: "single",
  score_options: "5,3,1,0",
  check_type: "manual",
  check_config: "",
};

function criterionToForm(c: Criterion): CriterionFormState {
  return {
    stt: c.stt,
    name: c.name,
    description: c.description ?? "",
    weight: c.weight != null ? String(c.weight) : "",
    include_in_total: c.include_in_total,
    selection_type: c.selection_type,
    score_options: c.score_options.map((o) => o.value).join(","),
    check_type: c.check_type,
    check_config: c.check_config ? JSON.stringify(c.check_config, null, 2) : "",
  };
}

function formToPayload(f: CriterionFormState) {
  return {
    stt: Number(f.stt),
    name: f.name,
    description: f.description,
    weight: f.weight.trim() === "" ? null : Number(f.weight),
    include_in_total: f.include_in_total,
    selection_type: f.selection_type,
    score_options: f.score_options
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean)
      .map((v) => ({ value: Number(v), label: v })),
    check_type: f.check_type,
    check_config: f.check_type === "keyword" && f.check_config.trim() !== "" ? JSON.parse(f.check_config) : null,
  };
}

export default function CriteriaPage() {
  const [sets, setSets] = useState<CriteriaSet[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [setDetail, setSetDetail] = useState<CriteriaSetWithCriteria | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<CriterionFormState>(emptyForm);
  const [addingNew, setAddingNew] = useState(false);
  const [newForm, setNewForm] = useState<CriterionFormState>(emptyForm);
  const [error, setError] = useState("");
  const [newSetCode, setNewSetCode] = useState("");
  const [newSetName, setNewSetName] = useState("");
  const [contextMenu, setContextMenu] = useState<ContextMenuState | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  const loadSets = async () => {
    const data = await CriteriaApi.listSets();
    setSets(data);
    if (!selectedId && data.length > 0) setSelectedId(data[0].id);
  };

  const loadDetail = async (id: string) => {
    if (!id) return;
    const detail = await CriteriaApi.getSet(id);
    setSetDetail(detail);
  };

  useEffect(() => {
    loadSets();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (selectedId) loadDetail(selectedId);
  }, [selectedId]);

  useEffect(() => {
    if (!contextMenu) return;
    const closeOnOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setContextMenu(null);
    };
    const closeOnEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") setContextMenu(null);
    };
    document.addEventListener("mousedown", closeOnOutside);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("mousedown", closeOnOutside);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [contextMenu]);

  const createSet = async () => {
    if (!newSetCode.trim() || !newSetName.trim()) return;
    const created = await CriteriaApi.createSet({
      code: newSetCode.trim(),
      name: newSetName.trim(),
      max_score: 5,
      thresholds: [
        { min: 5, label: "Xuất sắc" },
        { min: 4, label: "Tốt" },
        { min: 3, label: "Đạt yêu cầu" },
        { min: 2, label: "Đạt một phần" },
        { min: 0, label: "Không đạt" },
      ],
      call_content_types: [],
      failed_point_tags: [],
    });
    setNewSetCode("");
    setNewSetName("");
    await loadSets();
    setSelectedId(created.id);
  };

  const startEdit = (c: Criterion) => {
    setEditingId(c.id);
    setEditForm(criterionToForm(c));
    setError("");
    setContextMenu(null);
  };

  const handleContextMenu = (e: React.MouseEvent, c: Criterion) => {
    e.preventDefault();
    setContextMenu({ criterionId: c.id, x: e.clientX, y: e.clientY });
  };

  const saveEdit = async () => {
    if (!editingId) return;
    setError("");
    try {
      await CriteriaApi.updateCriterion(editingId, formToPayload(editForm));
      setEditingId(null);
      if (selectedId) await loadDetail(selectedId);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "JSON cấu hình không hợp lệ hoặc lỗi lưu");
    }
  };

  const removeCriterion = async (id: string) => {
    setContextMenu(null);
    if (!confirm("Xoá tiêu chí này?")) return;
    await CriteriaApi.deleteCriterion(id);
    if (selectedId) await loadDetail(selectedId);
  };

  const saveNew = async () => {
    if (!selectedId) return;
    setError("");
    try {
      await CriteriaApi.addCriterion(selectedId, formToPayload(newForm));
      setAddingNew(false);
      setNewForm({ ...emptyForm, stt: (setDetail?.criteria.length ?? 0) + 1 });
      await loadDetail(selectedId);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "JSON cấu hình không hợp lệ hoặc lỗi lưu");
    }
  };

  return (
    <div>
      <section className="card">
        <h2>Khung tiêu chí chấm điểm</h2>
        <div className="field-row">
          <div className="field">
            <label>Chọn bộ tiêu chí</label>
            <select value={selectedId} onChange={(e) => setSelectedId(e.target.value)}>
              {sets.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} ({s.code})
                </option>
              ))}
            </select>
          </div>
        </div>

        <details className="new-set-form">
          <summary>+ Tạo bộ tiêu chí mới (vd: EMAIL, CHAT...)</summary>
          <div className="field-row">
            <input placeholder="Mã (code), vd: CHAT" value={newSetCode} onChange={(e) => setNewSetCode(e.target.value)} />
            <input placeholder="Tên hiển thị, vd: CHAT" value={newSetName} onChange={(e) => setNewSetName(e.target.value)} />
            <button onClick={createSet}>Tạo</button>
          </div>
        </details>
      </section>

      {error && <p className="error">{error}</p>}

      {setDetail && (
        <section className="card">
          <h3>Danh sách tiêu chí — {setDetail.name}</h3>
          <table className="table criteria-table">
            <thead>
              <tr>
                <th>STT</th>
                <th>Tên tiêu chí</th>
                <th>Trọng số</th>
                <th>Tính vào tổng</th>
                <th>Thang điểm</th>
                <th>Kiểm tra</th>
              </tr>
            </thead>
            <tbody>
              {setDetail.criteria.map((c) =>
                editingId === c.id ? (
                  <tr key={c.id} className="editing-row">
                    <td colSpan={6}>
                      <CriterionEditor form={editForm} setForm={setEditForm} />
                      <div className="edit-actions">
                        <button onClick={saveEdit}>Lưu</button>
                        <button className="secondary" onClick={() => setEditingId(null)}>
                          Huỷ
                        </button>
                      </div>
                    </td>
                  </tr>
                ) : (
                  <tr
                    key={c.id}
                    className="criterion-row"
                    onContextMenu={(e) => handleContextMenu(e, c)}
                    title="Chuột phải để Sửa/Xoá"
                  >
                    <td>{c.stt}</td>
                    <td>{c.name}</td>
                    <td>{c.weight != null ? `${(c.weight * 100).toFixed(0)}%` : "-"}</td>
                    <td>{c.include_in_total ? "Có" : "Không"}</td>
                    <td>{c.score_options.map((o) => o.label).join(" / ")}</td>
                    <td>{c.check_type === "keyword" ? "Tự động (từ khóa)" : "Thủ công"}</td>
                  </tr>
                ),
              )}
            </tbody>
          </table>

          {contextMenu && (
            <div ref={menuRef} className="context-menu" style={{ top: contextMenu.y, left: contextMenu.x }}>
              <button
                onClick={() => {
                  const c = setDetail.criteria.find((x) => x.id === contextMenu.criterionId);
                  if (c) startEdit(c);
                }}
              >
                <IconEdit size={15} /> Sửa
              </button>
              <button className="danger" onClick={() => removeCriterion(contextMenu.criterionId)}>
                <IconTrash size={15} /> Xoá
              </button>
            </div>
          )}

          {addingNew ? (
            <div className="add-new-block">
              <h4>Thêm tiêu chí mới</h4>
              <CriterionEditor form={newForm} setForm={setNewForm} />
              <div className="edit-actions">
                <button onClick={saveNew}>Lưu tiêu chí mới</button>
                <button className="secondary" onClick={() => setAddingNew(false)}>
                  Huỷ
                </button>
              </div>
            </div>
          ) : (
            <button
              onClick={() => {
                setNewForm({ ...emptyForm, stt: (setDetail.criteria.length ?? 0) + 1 });
                setAddingNew(true);
              }}
            >
              <IconPlus size={15} /> Thêm tiêu chí
            </button>
          )}
        </section>
      )}
    </div>
  );
}

function CriterionEditor({
  form,
  setForm,
}: {
  form: CriterionFormState;
  setForm: (f: CriterionFormState) => void;
}) {
  return (
    <div className="criterion-editor">
      <div className="field-row">
        <div className="field">
          <label>STT</label>
          <input type="number" value={form.stt} onChange={(e) => setForm({ ...form, stt: Number(e.target.value) })} />
        </div>
        <div className="field grow">
          <label>Tên tiêu chí</label>
          <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        </div>
        <div className="field">
          <label>Trọng số (0-1, để trống nếu không tính)</label>
          <input value={form.weight} onChange={(e) => setForm({ ...form, weight: e.target.value })} placeholder="vd: 0.2" />
        </div>
      </div>

      <div className="field">
        <label>Mô tả thang điểm chi tiết</label>
        <textarea rows={4} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
      </div>

      <div className="field-row">
        <div className="field">
          <label>Các mốc điểm (phân cách bằng dấu phẩy)</label>
          <input
            value={form.score_options}
            onChange={(e) => setForm({ ...form, score_options: e.target.value })}
            placeholder="5,3,1,0"
          />
        </div>
        <div className="field">
          <label>
            <input
              type="checkbox"
              checked={form.include_in_total}
              onChange={(e) => setForm({ ...form, include_in_total: e.target.checked })}
            />{" "}
            Tính vào tổng điểm
          </label>
        </div>
        <div className="field">
          <label>Cách chấm</label>
          <select value={form.check_type} onChange={(e) => setForm({ ...form, check_type: e.target.value as any })}>
            <option value="manual">Thủ công (QA tự tick)</option>
            <option value="keyword">Tự động theo từ khóa (không AI)</option>
          </select>
        </div>
      </div>

      {form.check_type === "keyword" && (
        <div className="field">
          <label>
            Cấu hình từ khóa (JSON) — vd nhóm bắt buộc/không bắt buộc, điểm khi đạt đủ / đạt một phần / không đạt
          </label>
          <textarea
            rows={8}
            className="mono"
            value={form.check_config}
            onChange={(e) => setForm({ ...form, check_config: e.target.value })}
            placeholder={`{
  "groups": [
    {"name": "Lời chào", "keywords": ["xin chào", "chào anh"], "required": true}
  ],
  "score_full": 5,
  "score_partial": 3,
  "score_none": 0
}`}
          />
        </div>
      )}
    </div>
  );
}
