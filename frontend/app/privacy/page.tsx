export const metadata = { title: "Chính sách bảo mật · Mình Đi Đâu Thế" };

export default function PrivacyPage() {
  return <main className="card legal-page">
    <div className="eyebrow">Phiên bản 2026-08-05</div>
    <h1>Chính sách bảo mật</h1>
    <p className="lead">Bản chính sách minh bạch dữ liệu dành cho môi trường thử nghiệm. Trước khi vận hành thương mại, đơn vị vận hành phải bổ sung pháp nhân, đầu mối bảo vệ dữ liệu và hoàn tất đánh giá pháp lý.</p>
    <h2>Dữ liệu chúng tôi xử lý</h2>
    <p>Thông tin chuyến đi, vị trí bạn chủ động cung cấp, lịch sử chỉnh sửa, bình luận, phản hồi và mã phiên được dùng để tạo và đồng bộ lịch trình. Khi đăng nhập Google, hệ thống nhận mã định danh, email đã xác minh và tên hiển thị; không nhận mật khẩu Google.</p>
    <h2>Mục đích và thời hạn</h2>
    <p>Dữ liệu chỉ được dùng để lập kế hoạch, cộng tác, nhắc chuyến, hỗ trợ đặt dịch vụ và bảo vệ hệ thống. Kế hoạch ẩn danh có thời hạn mặc định 30 ngày theo thiết kế HLD; dữ liệu tài khoản được giữ cho tới khi người dùng yêu cầu xóa hoặc chính sách lưu trữ vận hành quy định ngắn hơn.</p>
    <h2>Nhà cung cấp và chuyển dữ liệu</h2>
    <p>Tùy cấu hình, dữ liệu tối thiểu có thể được gửi tới Google (đăng nhập), DeepSeek (tinh chỉnh văn bản), Open‑Meteo (thời tiết), OpenStreetMap/OSRM (địa điểm và tuyến đường), Amadeus (tìm kiếm dịch vụ), PostgreSQL và Redis. Giá và tình trạng chỗ không được gửi cho AI để bịa hoặc xác nhận thay nhà cung cấp.</p>
    <h2>Quyền và lựa chọn của bạn</h2>
    <p>Bạn có thể không đăng nhập, không cấp vị trí chính xác, tải bản sao lịch trình, chỉnh sửa dữ liệu hoặc yêu cầu truy cập, sửa, rút lại đồng ý và xóa dữ liệu. Việc rút đồng ý không làm thay đổi tính hợp pháp của xử lý đã diễn ra trước đó.</p>
    <h2>An toàn và liên hệ</h2>
    <p>Hệ thống áp dụng phân quyền chủ sở hữu, liên kết chia sẻ chỉ đọc, giới hạn tốc độ, nhật ký chi phí và không lưu bí mật trong mã nguồn. Kênh yêu cầu quyền riêng tư và thời hạn phản hồi phải được đơn vị triển khai cấu hình trước khi production.</p>
  </main>;
}
