# CallMetrics — App chấm điểm cuộc gọi CSKH / bán hàng

Ứng dụng dockerized để tải lên bản ghi âm cuộc gọi (CSKH, bán hàng, lên đơn...), tự động chuyển giọng nói thành văn bản (Speech-to-Text chạy local bằng faster-whisper, không tốn phí), rồi **tự động chấm điểm toàn bộ tiêu chí bằng AI (Claude)** theo đúng khung tiêu chí trong file `KHUNG CHẤM ĐIỂM.xlsx` — QA chỉ cần xem lại, sửa nếu cần, rồi copy điểm vào portal công ty.

## Kiến trúc

- **backend/** — FastAPI (Python) + PostgreSQL. STT dùng [faster-whisper](https://github.com/SYSTRAN/faster-whisper) chạy local trên CPU.
- **frontend/** — React + Vite + TypeScript, build tĩnh, phục vụ qua Nginx (Nginx cũng proxy `/api` sang backend).
- **docker-compose.yml** — điều phối 3 service: `db` (Postgres), `backend`, `frontend`.

## Chạy ứng dụng

**Cách 1 — chỉ cần cài [Docker Desktop](https://www.docker.com/products/docker-desktop/), sau đó double-click `deploy.bat`** (Windows). App sẽ tự build và khởi động toàn bộ (Postgres + backend + frontend). Lần đầu chạy sẽ mất vài phút để tải/build image, các lần sau nhanh hơn nhiều nhờ cache.

**Cách 2 — dòng lệnh** (mọi hệ điều hành, tương đương `deploy.sh`):

```bash
docker compose up -d --build
```

Sau khi chạy xong, mở trình duyệt vào **http://localhost:8081**.

Nếu port 8081 bị trùng với ứng dụng khác trên máy, copy `.env.example` thành `.env` rồi sửa `FRONTEND_PORT=` sang port khác, chạy lại `deploy.bat`/lệnh trên là xong — không cần sửa gì trong `docker-compose.yml`.

Muốn tắt app: `docker compose down`.

Lần đầu transcribe một bản ghi, container backend sẽ tải model Whisper (`medium` mặc định, ~1.5GB) về, có thể mất vài phút; các lần sau dùng cache (volume `whisper_cache`).

### Bật chấm điểm bằng AI (khuyến nghị)

1. Lấy API key tại https://console.anthropic.com/settings/keys (tính phí theo tài khoản Anthropic của bạn, theo lượng transcript gửi đi — không tính theo dung lượng audio).
2. Copy `.env.example` thành `.env`, điền vào `ANTHROPIC_API_KEY=sk-ant-...`.
3. Chạy lại `deploy.bat` (hoặc `docker compose up -d --build`).

### Hoặc: chấm bằng AI chạy local (Ollama, miễn phí)

Không muốn tốn phí API thì có thể chạy model AI ngay trên máy qua [Ollama](https://ollama.com) (chạy sẵn trong Docker, không cần cài thêm gì). Thêm vào `.env`:

```
LLM_PROVIDER=ollama
COMPOSE_PROFILES=ollama
OLLAMA_MODEL=qwen2.5:7b
```

rồi chạy lại `deploy.bat`. Lần đầu sẽ tự tải model (~4.7GB với `qwen2.5:7b`). Đánh đổi so với Claude:

- **Chậm hơn nhiều** nếu máy không có GPU: mỗi lần chấm có thể mất vài phút đến hơn 10 phút trên CPU laptop (nút "Tạo phiên chấm điểm" sẽ chờ trong lúc đó). `qwen2.5:3b` nhanh hơn ~2 lần nhưng chấm kém hơn.
- **Chấm kém chính xác hơn** Claude, nhất là với tiêu chí cần hiểu ngữ cảnh — QA càng cần đọc kỹ bằng chứng AI trích dẫn.
- Cần RAM: model 7B + Whisper `medium` dùng khoảng 8–10GB.

Muốn quay về Claude: đổi `LLM_PROVIDER=anthropic` và xoá dòng `COMPOSE_PROFILES`.

Không cấu hình AI thì app vẫn chạy bình thường, chỉ là quay về chấm bằng rule từ khóa (như bản trước) cho các tiêu chí đối chiếu được, còn lại để QA tự chấm tay.

Dữ liệu tiêu chí trong `backend/app/seed/seed_data.json` (chuyển thể từ `KHUNG CHẤM ĐIỂM.xlsx`, 2 bộ **CALL IN** và **CALL OUT**) được tự động nạp vào DB khi backend khởi động lần đầu (không ghi đè nếu đã tồn tại).

## Cách dùng

1. **Tab "Chấm điểm"**: chọn bộ tiêu chí (CALL IN / CALL OUT), nhập tên người chấm, rồi chọn 1 trong 2 cách thêm bản ghi:
   - **Tải file lên**: chọn file ghi âm (mp3/wav/m4a/ogg/flac/aac/wma) từ máy.
   - **Dán URL nghe online**: dùng khi công ty chặn tải file — dán URL nghe trực tiếp lấy từ portal ghi âm (URL phải tự truy cập được, không cần đăng nhập/cookie — kiểm tra bằng cách mở URL đó ở trình duyệt ẩn danh, nếu vẫn nghe được thì dùng được). Backend sẽ tự tải file từ URL này về để xử lý, y hệt như trình duyệt "nghe online", không cần bấm nút Download nào.
2. App tự động chuyển giọng nói → văn bản (trạng thái "Đang chuyển giọng nói..."). Khi xong, bấm "Chấm điểm" để vào trang chi tiết.
3. Trang chi tiết: nghe lại ghi âm (audio player, click vào từng đoạn transcript để tua tới đó), tạo phiên chấm điểm. Nếu đã cấu hình `ANTHROPIC_API_KEY`, AI sẽ đọc transcript và **tự chấm toàn bộ tiêu chí** (badge tím "Chấm bởi AI", kèm nhận xét trích từ transcript làm bằng chứng), đồng thời tự gợi ý phân loại nội dung cuộc gọi, điểm không đạt và nhận xét tổng thể — QA xem lại, sửa điểm/nhận xét nếu AI chấm chưa đúng, rồi copy sang portal công ty. Nếu chưa cấu hình AI, các tiêu chí đối chiếu được bằng từ khóa (badge xanh lá "Tự động kiểm tra") vẫn tự điền sẵn, còn lại QA tự chọn điểm.
4. Điền/sửa phân loại nội dung cuộc gọi, tick các điểm không đạt (nếu có), nhận xét tổng thể, rồi "Hoàn tất chấm điểm" — app tự tính tổng điểm theo trọng số và xếp loại.
5. **Tab "Khung tiêu chí"**: xem/sửa/xoá/thêm tiêu chí cho từng bộ (tên, mô tả thang điểm, trọng số, có tính vào tổng hay không, các mốc điểm, và cấu hình từ khóa tự động chấm). Có thể tạo bộ tiêu chí mới hoàn toàn (vd. CHAT, EMAIL...).

## Giới hạn quan trọng — đọc trước khi dùng thật

- **AI có thể chấm sai.** Claude đọc transcript và chấm theo đúng mô tả thang điểm của từng tiêu chí, nhưng vẫn là một mô hình AI — có thể hiểu sai ngữ cảnh, bỏ sót chi tiết, hoặc chấm khác với con người trong trường hợp mập mờ. Điểm AI đưa ra **luôn ở dạng gợi ý có thể sửa**, không tự khoá — QA nên đọc qua bằng chứng (evidence) AI trích dẫn trước khi tin và copy sang portal, đặc biệt với các tiêu chí trọng số cao.
- **Chất lượng transcript quyết định chất lượng điểm AI chấm** — AI chỉ đọc được transcript, không nghe được giọng điệu/cảm xúc thật trong ghi âm. Transcript sai chính tả nhiều do STT sẽ khiến AI chấm sai theo. Xem phần dưới để tăng độ chính xác STT.
- **Tốn phí theo tài khoản Anthropic của bạn** — mỗi cuộc gọi chấm điểm là một lần gọi API (gửi transcript dạng văn bản, không gửi audio), chi phí phụ thuộc độ dài transcript. Không cấu hình `ANTHROPIC_API_KEY` thì không tốn phí, app quay về chấm bằng từ khóa (rule-based, không AI) như trước.

### Tăng độ chính xác transcript (STT)

Model mặc định đã đổi sang `medium` (cân bằng tốc độ/độ chính xác cho CPU). Đã test thực nghiệm: với model `medium` + gợi ý từ vựng (`WHISPER_INITIAL_PROMPT`, đã có sẵn từ vựng CSKH tiếng Việt mặc định), transcript khớp chính xác 100% với một đoạn hội thoại mẫu — trong khi model `small` cũ bị sai nhiều lỗi chính tả dấu (vd "khuyến mãi" → "huyền mãi").

Nếu vẫn còn nhiều lỗi chính tả (giọng địa phương, ghi âm ồn, nhiều tạp âm...), có thể tăng thêm bằng cách sửa trong `.env`:

```
WHISPER_MODEL_SIZE=large-v3
WHISPER_INITIAL_PROMPT=Tên sản phẩm, tên công ty, thuật ngữ riêng của công ty bạn...
```

`large-v3` chính xác hơn nữa nhưng chậm hơn đáng kể trên CPU (không có GPU) — cân nhắc theo cấu hình máy.

## Ghi chú kỹ thuật khác

- File ghi âm lưu tại `./storage/audio` trên máy host (bind mount), xem/backup trực tiếp được.
- Không có xác thực đăng nhập (nội bộ, tên người chấm chỉ là text tự nhập) — nếu triển khai ra ngoài môi trường tin cậy, cần thêm auth trước khi public port 8081/8000.
- Transcribe chạy nền (background task) trong tiến trình backend, không dùng queue riêng (Celery/Redis) — phù hợp quy mô nhỏ/vừa; nếu tải cao (nhiều file cùng lúc) có thể cần nâng cấp sang hàng đợi riêng.
- **Thêm bản ghi bằng URL**: backend tải file qua `POST /api/records/from-url`, giới hạn 300MB, timeout kết nối 15s, có chặn cơ bản SSRF (chỉ cho http/https, từ chối URL trỏ vào địa chỉ mạng nội bộ/loopback). Nếu công ty chặn download vì lý do bảo mật/tuân thủ dữ liệu khách hàng, nên xác nhận với IT/quản trị hệ thống ghi âm rằng việc app tự động lấy file qua URL công khai (không cần đăng nhập) là được phép, trước khi dùng chính thức.
- **Chấm điểm AI**: dùng model `claude-opus-5` (đổi qua `ANTHROPIC_MODEL` trong `.env` nếu cần), 1 lần gọi API cho toàn bộ tiêu chí của 1 cuộc gọi (không phải gọi riêng từng tiêu chí), dùng structured output (JSON schema) nên điểm luôn khớp đúng 1 trong các mốc điểm đã cấu hình cho tiêu chí đó — không thể tự bịa ra điểm số lạ. Nếu gọi AI lỗi (hết quota, mất mạng, key sai...) app tự động rơi về chấm bằng rule từ khóa, không làm crash việc tạo phiên chấm điểm.
