# CallMetrics — App chấm điểm cuộc gọi CSKH / bán hàng

Ứng dụng dockerized để tải lên bản ghi âm cuộc gọi (CSKH, bán hàng, lên đơn...), tự động chuyển giọng nói thành văn bản (Speech-to-Text chạy **local, không gọi AI/LLM ngoài, không tốn phí API**), tự động chấm các tiêu chí đối chiếu được bằng từ khóa, và cung cấp giao diện cho QA chấm các tiêu chí còn lại theo khung tiêu chí trong file `KHUNG CHẤM ĐIỂM.xlsx`.

## Kiến trúc

- **backend/** — FastAPI (Python) + PostgreSQL. STT dùng [faster-whisper](https://github.com/SYSTRAN/faster-whisper) chạy local trên CPU.
- **frontend/** — React + Vite + TypeScript, build tĩnh, phục vụ qua Nginx (Nginx cũng proxy `/api` sang backend).
- **docker-compose.yml** — điều phối 3 service: `db` (Postgres), `backend`, `frontend`.

## Chạy ứng dụng

```bash
docker compose up -d --build
```

- Giao diện: http://localhost:8081
- API: http://localhost:8000/api (chỉ cần khi debug trực tiếp, frontend đã tự gọi qua proxy `/api`)

Lần đầu transcribe một bản ghi, container backend sẽ tải model Whisper (`small` mặc định, ~500MB) về, có thể mất vài phút; các lần sau dùng cache (volume `whisper_cache`).

Dữ liệu tiêu chí trong `backend/app/seed/seed_data.json` (chuyển thể từ `KHUNG CHẤM ĐIỂM.xlsx`, 2 bộ **CALL IN** và **CALL OUT**) được tự động nạp vào DB khi backend khởi động lần đầu (không ghi đè nếu đã tồn tại).

## Cách dùng

1. **Tab "Chấm điểm"**: chọn file ghi âm (mp3/wav/m4a/ogg/flac/aac/wma), chọn bộ tiêu chí (CALL IN / CALL OUT), nhập tên người chấm, bấm Tải lên.
2. App tự động chuyển giọng nói → văn bản (trạng thái "Đang chuyển giọng nói..."). Khi xong, bấm "Chấm điểm" để vào trang chi tiết.
3. Trang chi tiết: nghe lại ghi âm (audio player, click vào từng đoạn transcript để tua tới đó), tạo phiên chấm điểm. App sẽ tự điền sẵn điểm cho các tiêu chí có gắn nhãn **"Tự động kiểm tra"** (dựa trên đối chiếu từ khóa với transcript, kèm trích đoạn làm bằng chứng) — QA có thể sửa lại nếu auto-check chưa đúng. Các tiêu chí còn lại QA đọc transcript/nghe lại và tự chọn điểm.
4. Điền phân loại nội dung cuộc gọi, tick các điểm không đạt (nếu có), nhận xét tổng thể, rồi "Hoàn tất chấm điểm" — app tự tính tổng điểm theo trọng số và xếp loại.
5. **Tab "Khung tiêu chí"**: xem/sửa/xoá/thêm tiêu chí cho từng bộ (tên, mô tả thang điểm, trọng số, có tính vào tổng hay không, các mốc điểm, và cấu hình từ khóa tự động chấm). Có thể tạo bộ tiêu chí mới hoàn toàn (vd. CHAT, EMAIL...).

## Giới hạn quan trọng — đọc trước khi dùng thật

App **không dùng AI/LLM** để "hiểu" và chấm điểm theo yêu cầu ban đầu. Việc tự động chấm chỉ áp dụng được cho các tiêu chí có thể đối chiếu bằng **từ khóa/cụm từ xuất hiện trong transcript** (vd: có chào hỏi, có nhắc chương trình ưu đãi, có lời chào tạm biệt). Các tiêu chí mang tính cảm tính/ngữ nghĩa như "kỹ năng giao tiếp", "linh hoạt xử lý tình huống", "tư vấn phù hợp với hoàn cảnh khách hàng" (thường chiếm tỉ trọng điểm cao nhất trong khung) **không thể chấm chính xác bằng rule từ khóa** — app để mặc định các tiêu chí này ở chế độ thủ công, hiển thị transcript để QA đọc nhanh và tự chấm, thay vì tự ý gán điểm sai.

Độ chính xác STT tiếng Việt của model `small` là mức trung bình, đặc biệt với giọng địa phương, nhiều tạp âm, hoặc ghi âm chất lượng thấp. Có thể tăng độ chính xác bằng cách đổi biến môi trường `WHISPER_MODEL_SIZE` sang `medium` hoặc `large-v3` (đánh đổi: chậm hơn, cần nhiều RAM/CPU hơn) — sửa trong `docker-compose.yml` hoặc file `.env`:

```
WHISPER_MODEL_SIZE=medium
```

## Ghi chú kỹ thuật khác

- File ghi âm lưu tại `./storage/audio` trên máy host (bind mount), xem/backup trực tiếp được.
- Không có xác thực đăng nhập (nội bộ, tên người chấm chỉ là text tự nhập) — nếu triển khai ra ngoài môi trường tin cậy, cần thêm auth trước khi public port 8081/8000.
- Transcribe chạy nền (background task) trong tiến trình backend, không dùng queue riêng (Celery/Redis) — phù hợp quy mô nhỏ/vừa; nếu tải cao (nhiều file cùng lúc) có thể cần nâng cấp sang hàng đợi riêng.
