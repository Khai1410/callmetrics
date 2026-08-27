import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { CriteriaApi, RecordsApi, ScoringApi } from "../api/client";
import type { CriteriaSet, RecordItem, ScoringSession } from "../api/types";

const STATUS_LABEL: Record<string, string> = {
  uploaded: "Đã tải lên, chờ xử lý",
  fetching: "Đang tải ghi âm từ URL...",
  transcribing: "Đang chuyển giọng nói thành văn bản...",
  transcribed: "Đã có transcript, sẵn sàng chấm điểm",
  failed: "Lỗi xử lý",
};

export default function RecordsListPage() {
  const [sets, setSets] = useState<CriteriaSet[]>([]);
  const [records, setRecords] = useState<RecordItem[]>([]);
  const [sessions, setSessions] = useState<ScoringSession[]>([]);
  const [source, setSource] = useState<"file" | "url">("file");
  const [file, setFile] = useState<File | null>(null);
  const [recordingUrl, setRecordingUrl] = useState("");
  const [criteriaSetId, setCriteriaSetId] = useState("");
  const [uploadedBy, setUploadedBy] = useState("");
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");

  const loadAll = async () => {
    const [setsData, recordsData, sessionsData] = await Promise.all([
      CriteriaApi.listSets(),
      RecordsApi.list(),
      ScoringApi.list(),
    ]);
    setSets(setsData);
    setRecords(recordsData);
    setSessions(sessionsData);
    if (!criteriaSetId && setsData.length > 0) setCriteriaSetId(setsData[0].id);
  };

  useEffect(() => {
    loadAll();
    const interval = setInterval(loadAll, 5000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const latestSessionFor = (recordId: string) =>
    sessions.filter((s) => s.record_id === recordId).sort((a, b) => (a.created_at < b.created_at ? 1 : -1))[0];

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!criteriaSetId) {
      setError("Vui lòng chọn bộ tiêu chí.");
      return;
    }
    if (source === "file" && !file) {
      setError("Vui lòng chọn file ghi âm.");
      return;
    }
    if (source === "url" && !recordingUrl.trim()) {
      setError("Vui lòng dán URL ghi âm.");
      return;
    }
    setUploading(true);
    try {
      if (source === "file" && file) {
        await RecordsApi.upload(file, criteriaSetId, uploadedBy);
        setFile(null);
        (document.getElementById("file-input") as HTMLInputElement).value = "";
      } else {
        await RecordsApi.uploadFromUrl(recordingUrl.trim(), criteriaSetId, uploadedBy);
        setRecordingUrl("");
      }
      await loadAll();
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Không thể thêm bản ghi");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div>
      <section className="card">
        <h2>Thêm bản ghi âm để chấm điểm</h2>
        <div className="source-toggle">
          <button
            type="button"
            className={source === "file" ? "" : "secondary"}
            onClick={() => setSource("file")}
          >
            Tải file lên
          </button>
          <button
            type="button"
            className={source === "url" ? "" : "secondary"}
            onClick={() => setSource("url")}
          >
            Dán URL nghe online
          </button>
        </div>
        <form className="upload-form" onSubmit={handleUpload}>
          {source === "file" ? (
            <div className="field">
              <label>File ghi âm (mp3, wav, m4a...)</label>
              <input
                id="file-input"
                type="file"
                accept=".mp3,.wav,.m4a,.ogg,.flac,.aac,.wma"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
            </div>
          ) : (
            <div className="field grow">
              <label>URL nghe ghi âm online (lấy từ portal, không cần đăng nhập)</label>
              <input
                type="text"
                value={recordingUrl}
                onChange={(e) => setRecordingUrl(e.target.value)}
                placeholder="https://portal.example.com/recordings/xxx.mp3?token=..."
              />
            </div>
          )}
          <div className="field">
            <label>Loại cuộc gọi / bộ tiêu chí</label>
            <select value={criteriaSetId} onChange={(e) => setCriteriaSetId(e.target.value)}>
              {sets.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Người chấm (tên/email)</label>
            <input value={uploadedBy} onChange={(e) => setUploadedBy(e.target.value)} placeholder="vd: qa.hoa" />
          </div>
          <button type="submit" disabled={uploading}>
            {uploading ? "Đang xử lý..." : source === "file" ? "Tải lên" : "Thêm từ URL"}
          </button>
          {error && <p className="error">{error}</p>}
        </form>
      </section>

      <section className="card">
        <h2>Danh sách bản ghi</h2>
        <table className="table">
          <thead>
            <tr>
              <th>File</th>
              <th>Bộ tiêu chí</th>
              <th>Trạng thái</th>
              <th>Điểm</th>
              <th>Xếp loại</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {records.map((r) => {
              const set = sets.find((s) => s.id === r.criteria_set_id);
              const session = latestSessionFor(r.id);
              return (
                <tr key={r.id}>
                  <td>{r.original_filename}</td>
                  <td>{set?.name ?? "-"}</td>
                  <td>
                    <span className={`badge badge-${r.status}`}>{STATUS_LABEL[r.status] ?? r.status}</span>
                    {r.status === "failed" && r.error_message && (
                      <div className="error-inline">{r.error_message}</div>
                    )}
                  </td>
                  <td>{session?.total_score ?? "-"}</td>
                  <td>{session?.classification ?? "-"}</td>
                  <td>
                    <Link to={`/records/${r.id}`}>
                      <button disabled={r.status === "uploaded" || r.status === "fetching" || r.status === "transcribing"}>
                        Chấm điểm
                      </button>
                    </Link>
                  </td>
                </tr>
              );
            })}
            {records.length === 0 && (
              <tr>
                <td colSpan={6}>Chưa có bản ghi nào.</td>
              </tr>
            )}
          </tbody>
        </table>
      </section>
    </div>
  );
}
