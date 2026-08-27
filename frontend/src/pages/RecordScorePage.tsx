import { useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { CriteriaApi, RecordsApi, ScoringApi } from "../api/client";
import type { CriteriaSet, CriteriaSetWithCriteria, RecordDetail, ScoringSession } from "../api/types";

export default function RecordScorePage() {
  const { id } = useParams<{ id: string }>();
  const [record, setRecord] = useState<RecordDetail | null>(null);
  const [criteriaSet, setCriteriaSet] = useState<CriteriaSetWithCriteria | null>(null);
  const [allSets, setAllSets] = useState<CriteriaSet[]>([]);
  const [session, setSession] = useState<ScoringSession | null>(null);
  const [scorerName, setScorerName] = useState("");
  const [error, setError] = useState("");
  const [editingSet, setEditingSet] = useState(false);
  const [pendingSetId, setPendingSetId] = useState("");
  const audioRef = useRef<HTMLAudioElement>(null);

  const loadRecord = async () => {
    if (!id) return;
    const rec = await RecordsApi.get(id);
    setRecord(rec);
    return rec;
  };

  useEffect(() => {
    CriteriaApi.listSets().then(setAllSets);
  }, []);

  useEffect(() => {
    loadRecord();
    const interval = setInterval(async () => {
      const rec = await loadRecord();
      if (rec && rec.status !== "transcribing" && rec.status !== "uploaded" && rec.status !== "fetching") {
        clearInterval(interval);
      }
    }, 4000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  useEffect(() => {
    if (record) {
      CriteriaApi.getSet(record.criteria_set_id).then(setCriteriaSet);
      ScoringApi.list().then((all) => {
        const mine = all
          .filter((s) => s.record_id === record.id)
          .sort((a, b) => (a.created_at < b.created_at ? 1 : -1));
        const draft = mine.find((s) => s.status === "draft");
        setSession(draft ?? mine[0] ?? null);
      });
    }
  }, [record?.id, record?.status]);

  const criteriaById = useMemo(() => {
    const map = new Map<string, CriteriaSetWithCriteria["criteria"][number]>();
    criteriaSet?.criteria.forEach((c) => map.set(c.id, c));
    return map;
  }, [criteriaSet]);

  const startSession = async () => {
    if (!record) return;
    setError("");
    try {
      const s = await ScoringApi.createSession(record.id, scorerName);
      setSession(s);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Không tạo được phiên chấm điểm");
    }
  };

  const setScore = async (criterionId: string, value: number) => {
    if (!session) return;
    await ScoringApi.updateItem(session.id, criterionId, { final_score: value });
    const refreshed = await ScoringApi.get(session.id);
    setSession(refreshed);
  };

  const setNote = async (criterionId: string, note: string) => {
    if (!session) return;
    await ScoringApi.updateItem(session.id, criterionId, { note });
  };

  const updateSessionField = async (payload: Partial<ScoringSession>) => {
    if (!session) return;
    const refreshed = await ScoringApi.update(session.id, payload);
    setSession(refreshed);
  };

  const toggleFailedTag = (tag: string) => {
    if (!session) return;
    const next = session.failed_point_tags.includes(tag)
      ? session.failed_point_tags.filter((t) => t !== tag)
      : [...session.failed_point_tags, tag];
    updateSessionField({ failed_point_tags: next });
  };

  const complete = async () => {
    if (!session) return;
    setError("");
    try {
      const s = await ScoringApi.complete(session.id);
      setSession(s);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Chưa thể hoàn tất");
    }
  };

  const saveCriteriaSet = async () => {
    if (!record || !pendingSetId || pendingSetId === record.criteria_set_id) {
      setEditingSet(false);
      return;
    }
    setError("");
    try {
      await RecordsApi.update(record.id, { criteria_set_id: pendingSetId });
      setSession(null);
      setEditingSet(false);
      await loadRecord();
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Không đổi được bộ tiêu chí");
    }
  };

  const deleteSession = async () => {
    if (!session) return;
    if (!confirm("Xoá phiên chấm điểm này? Bạn có thể tạo phiên mới ngay sau đó.")) return;
    await ScoringApi.delete(session.id);
    setSession(null);
  };

  const seek = (t: number) => {
    if (audioRef.current) {
      audioRef.current.currentTime = t;
      audioRef.current.play();
    }
  };

  if (!record) return <p>Đang tải...</p>;

  const readOnly = session?.status === "completed";
  const weightedTotal = criteriaSet
    ? criteriaSet.criteria
        .filter((c) => c.include_in_total)
        .reduce((sum, c) => sum + (c.weight ?? 0), 0)
    : 0;

  return (
    <div className="score-layout">
      <section className="card audio-panel">
        <h2>{record.original_filename}</h2>
        {editingSet ? (
          <div className="field-row inline-edit">
            <select value={pendingSetId} onChange={(e) => setPendingSetId(e.target.value)}>
              {allSets.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
            <button onClick={saveCriteriaSet}>Lưu</button>
            <button className="secondary" onClick={() => setEditingSet(false)}>
              Huỷ
            </button>
          </div>
        ) : (
          <p className="muted">
            Bộ tiêu chí: {record.criteria_set.name}{" "}
            <button
              className="link-btn"
              onClick={() => {
                setPendingSetId(record.criteria_set_id);
                setEditingSet(true);
              }}
            >
              Đổi
            </button>
          </p>
        )}
        <p className="muted">Trạng thái: {record.status}</p>

        {record.status === "fetching" && <p>Đang tải ghi âm từ URL, vui lòng chờ...</p>}
        {record.status === "transcribing" && <p>Đang chuyển giọng nói thành văn bản, vui lòng chờ...</p>}
        {record.status === "failed" && <p className="error">Lỗi: {record.error_message}</p>}

        {(record.status === "transcribed" || session) && (
          <>
            <audio ref={audioRef} controls src={RecordsApi.audioUrl(record.id)} style={{ width: "100%" }} />
            <div className="transcript-box">
              <h3>Transcript</h3>
              {record.transcript?.segments?.length ? (
                record.transcript.segments.map((seg, i) => (
                  <p key={i} className="segment" onClick={() => seek(seg.start)}>
                    <span className="ts">[{formatTime(seg.start)}]</span> {seg.text}
                  </p>
                ))
              ) : (
                <p className="muted">Chưa có transcript.</p>
              )}
            </div>
          </>
        )}
      </section>

      <section className="card score-panel">
        {!session && record.status === "transcribed" && (
          <div className="field">
            <h3>Bắt đầu chấm điểm</h3>
            <label>Tên người chấm</label>
            <input value={scorerName} onChange={(e) => setScorerName(e.target.value)} placeholder="vd: qa.hoa" />
            <button onClick={startSession}>Tạo phiên chấm điểm</button>
          </div>
        )}

        {error && <p className="error">{error}</p>}

        {session && criteriaSet && (
          <>
            <h3>Chấm điểm theo tiêu chí</h3>
            {criteriaSet.criteria.map((criterion) => {
              const item = session.items.find((i) => i.criterion_id === criterion.id);
              return (
                <div className="criterion-block" key={criterion.id}>
                  <div className="criterion-head">
                    <strong>
                      {criterion.stt}. {criterion.name}
                    </strong>
                    {criterion.include_in_total && criterion.weight != null && (
                      <span className="weight-tag">Trọng số {(criterion.weight * 100).toFixed(0)}%</span>
                    )}
                    {item?.auto_evidence?.startsWith("[AI]") ? (
                      <span className="auto-tag ai-tag">Chấm bởi AI</span>
                    ) : (
                      criterion.check_type === "keyword" && <span className="auto-tag">Tự động kiểm tra</span>
                    )}
                  </div>
                  <details>
                    <summary>Xem thang điểm chi tiết</summary>
                    <pre className="desc">{criterion.description}</pre>
                  </details>

                  {item?.auto_evidence && (
                    <div className="evidence">
                      <em>{item.auto_evidence.startsWith("[AI]") ? "Nhận xét của AI:" : "Kết quả kiểm tra tự động:"}</em>{" "}
                      {item.auto_evidence.replace(/^\[AI\]\s*/, "")}
                    </div>
                  )}

                  <div className="score-options">
                    {criterion.score_options.map((opt) => (
                      <label key={opt.value} className={item?.final_score === opt.value ? "selected" : ""}>
                        <input
                          type="radio"
                          name={`crit-${criterion.id}`}
                          checked={item?.final_score === opt.value}
                          disabled={readOnly}
                          onChange={() => setScore(criterion.id, opt.value)}
                        />
                        {opt.label} điểm
                      </label>
                    ))}
                  </div>

                  <input
                    className="note-input"
                    placeholder="Ghi chú (tuỳ chọn)"
                    defaultValue={item?.note ?? ""}
                    disabled={readOnly}
                    onBlur={(e) => setNote(criterion.id, e.target.value)}
                  />
                </div>
              );
            })}

            <div className="field">
              <label>Phân loại nội dung cuộc gọi</label>
              <select
                value={session.call_content_type ?? ""}
                disabled={readOnly}
                onChange={(e) => updateSessionField({ call_content_type: e.target.value })}
              >
                <option value="">-- chọn --</option>
                {criteriaSet.call_content_types.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </div>

            <div className="field">
              <label>Những điểm không đạt của cuộc gọi</label>
              <div className="tag-list">
                {criteriaSet.failed_point_tags.map((tag) => (
                  <label key={tag} className="tag-checkbox">
                    <input
                      type="checkbox"
                      checked={session.failed_point_tags.includes(tag)}
                      disabled={readOnly}
                      onChange={() => toggleFailedTag(tag)}
                    />
                    {tag}
                  </label>
                ))}
              </div>
            </div>

            <div className="field">
              <label>Nhận xét tổng thể</label>
              <textarea
                defaultValue={session.overall_comment ?? ""}
                disabled={readOnly}
                onBlur={(e) => updateSessionField({ overall_comment: e.target.value })}
              />
            </div>

            <div className="total-box">
              <div>
                Tổng điểm (trọng số đã cấu hình: {(weightedTotal * 100).toFixed(0)}%):{" "}
                <strong>{session.total_score ?? "-"}</strong>
              </div>
              <div>Xếp loại: <strong>{session.classification ?? "-"}</strong></div>
              <div>
                {!readOnly && <button onClick={complete}>Hoàn tất chấm điểm</button>}
                {readOnly && <span className="badge badge-transcribed">Đã hoàn tất</span>}
                <button className="secondary" onClick={deleteSession}>
                  Xoá phiên chấm điểm này
                </button>
              </div>
            </div>
          </>
        )}
      </section>
    </div>
  );
}

function formatTime(sec: number) {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}
