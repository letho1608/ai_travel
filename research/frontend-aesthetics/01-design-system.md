# Đánh giá Thẩm mỹ & Thiết kế Visual - Frontend Next.js

## 1. Tổng quan Design System

Tệp `app/globals.css` định nghĩa một design system cơ bản dựa trên CSS variables (tại dòng 1). Hệ màu sắc chủ đạo sử dụng Teal (#0f766e) cho màu nhấn (brand) và thang màu xanh đen/xám cho văn bản (ink, muted). 

Hệ thống được thiết kế theo hướng tiện ích, với các lớp (classes) chuyên biệt cho thành phần UI (planner, card, button). Tuy nhiên, có một số vấn đề về tính nhất quán, contrast và quản lý tokens cần được cải thiện để đạt mức độ thẩm mỹ chuyên nghiệp.

---

## 2. Các điểm cần cải thiện (Findings)

### Finding 1: Quản lý Design Tokens chưa toàn diện
- **Vị trí**: Dòng 1, `globals.css`
- **Mức độ**: Medium
- **Mô tả**: Biến CSS (CSS variables) định nghĩa chưa đầy đủ. Chỉ có một số biến màu sắc cơ bản: `--ink`, `--muted`, `--paper`, `--brand`, `--sun`, `--line`. Thiếu các biến cho:
  - Bảng màu đầy đủ (scale) cho các trạng thái (hover, active, focus, error, warning). Màu `#e4572e` (orange accent) không hề xuất hiện trong code hiện tại, màu lỗi (#b42318 ở dòng 1), focus outline (#54a692 ở dòng 19) đang bị hardcode.
  - Spacing (margins, paddings, gaps) hiện đang bị hardcode nhiều magic numbers rải rác: `24px`, `48px`, `14px`, `26px`, v.v.
  - Typography (font sizes, line heights) chưa có token: `21px`, `20px`, `17px`, `14px`, v.v.
  - Border radius cũng bị hardcode (28px, 14px, 22px, 18px, 12px, 10px).
- **Khuyên cải thiện**: Nên định nghĩa hệ thống token hoàn chỉnh. Ví dụ: `--spacing-sm`, `--spacing-md`, `--radius-md`, `--radius-lg`, `--text-base`, `--text-lg`. Thay thế toàn bộ magic numbers bằng các biến này để duy trì sự nhất quán, dễ maintain và tạo base chuẩn cho các component.

### Finding 2: Tương phản màu sắc (Contrast WCAG AA) chưa đạt chuẩn ở một số vùng
- **Vị trí**: Xuyên suốt `globals.css`
- **Mức độ**: High
- **Mô tả**: Tính toán tỉ lệ tương phản (relative luminance, công thức WCAG 2.1) giữa các màu sắc cho thấy có những cặp màu vi phạm tiêu chuẩn AA (tối thiểu 4.5:1 cho text thường, 3.1 cho text lớn).
    - **Tính toán thủ công:**
        - **Light mode:**
            - `--ink: #18332d` trên `--paper: #fffdf7`: Tương phản xuất sắc, > 10:1 (Pass).
            - `--brand: #0f766e` trên `--paper: #fffdf7`: Tương phản tốt, > 4.5:1 (Pass).
            - `--muted: #64746f` (0.392, 0.455, 0.435 -> Luminance ~0.18) trên `--paper: #fffdf7` (Luminance ~0.95): Tương phản khoảng `(0.95 + 0.05) / (0.18 + 0.05) = 4.34:1`. **(Fail AA cho text thường)**. Mức này chỉ suýt soát pass, nên làm đậm màu muted lên một chút, ví dụ `#52635e`.
            - Text trắng `#ffffff` (Luminance 1.0) trên `--brand: #0f766e` (0.059, 0.463, 0.431 -> Luminance ~0.15): Tương phản `(1.0 + 0.05) / (0.15 + 0.05) = 5.25:1`. (Pass AA).
            - Focus outline `#54a692` trên nền `#f0f4f2`: Tương phản kém, khó nhận biết trạng thái focus.
        - **Dark mode:**
            - `--brand: #38b8a8` (0.22, 0.72, 0.66 -> Luminance ~0.4) trên nền dark `--paper: #101a17` (Luminance ~0.01): Tương phản `(0.4 + 0.05) / (0.01 + 0.05) = 7.5:1` (Pass).
            - Text trắng `#ffffff` (trong class `.primary` dòng 59) trên nền `.primary` dark mode `--brand: #0f766e` (vẫn giữ `#0f766e` dòng 59): Tương phản 5.25:1. (Pass, nhưng màu `--brand` ở dark mode đã được đổi thành `#38b8a8` ở dòng 35, việc class `.primary` giữ cứng màu `#0f766e` dòng 59 có thể gây mất nhất quán về mặt visual).
            - `.muted` dark mode: `#9db0aa` trên nền `#101a17` có tương phản tốt.
            - Nút disabled (`opacity: .55`, dark: `opacity: .4` dòng 45) làm giảm mạnh contrast, có thể khó nhìn.
- **Khuyên cải thiện**:
  - Light mode: Đổi `--muted` thành `#54635e` để đảm bảo contrast ratio > 4.5:1.
  - Sửa trạng thái focus state (`.slot-select:focus-visible` dòng 19) sử dụng màu outline có độ tương phản cao hơn.

### Finding 3: Bóng đổ (Shadow/Depth) và Đường viền (Border) thiếu tính cấu trúc
- **Vị trí**: Dòng 1, dòng 3, dòng 38
- **Mức độ**: Medium
- **Mô tả**: Shadow được sử dụng một cách lẻ tẻ, ví dụ `.planner` (dòng 1) có `box-shadow: 0 24px 70px #164e3d1a`. Dark mode (dòng 38) đổi thành `0 24px 70px #00000055`. Box-shadow này khá đẹp và mềm mại, tạo chiều sâu tốt cho card chính. Tuy nhiên, nó là shadow duy nhất trong toàn hệ thống. Thiếu hệ thống shadow các cấp (elevation: sm, md, lg) cho các dropdown, tooltip, popover, hay các card phụ (`.card` chỉ có border, không shadow).
- **Khuyên cải thiện**: Nên định nghĩa một hệ thống elevation tokens (VD: `--shadow-sm`, `--shadow-md`, `--shadow-lg`) để tạo sự thống nhất. Các tương tác như hover trên card cũng có thể sử dụng shadow để tạo hiệu ứng nổi (lift).

### Finding 4: Spacing và Radius không theo grid chuẩn (Magic numbers)
- **Vị trí**: Dòng 1-33
- **Mức độ**: Medium
- **Mô tả**: Sử dụng rất nhiều giá trị spacing và radius lẻ, không thuộc hệ scale chuẩn (ví dụ 4px hoặc 8px baseline grid). 
    - Padding/Margin: `24px`, `48px`, `42px`, `14px`, `26px`, `7px`, `11px`, `13px`, `6px`, `18px`, `25px`, `34px`. Việc sử dụng các giá trị như 7px, 11px, 13px, 15px tạo cảm giác thiếu ngăn nắp và khó căn chỉnh pixel-perfect.
    - Radius: `28px`, `14px`, `22px`, `18px`, `12px`, `11px`, `10px`. Sự chênh lệch giữa các block kề nhau (VD: input radius 14px nằm trong planner radius 28px là hợp lý, nhưng card 22px, day-tabs 10px lại khá rời rạc).
- **Khuyên cải thiện**: Chuẩn hóa spacing và radius theo thang 4px (4, 8, 12, 16, 20, 24, 32...). VD: padding button 12px 16px thay vì 11px 13px.

### Finding 5: Dark Mode Implementation chưa nhất quán
- **Vị trí**: Dòng 34-68 (`@media (prefers-color-scheme: dark)`)
- **Mức độ**: Medium
- **Mô tả**: Việc override trực tiếp CSS selector ở cuối file làm tăng độ phức tạp khi scale hệ thống.
    - Dòng 59: `.primary { background: #0f766e; color: #fff }`. Mặc dù biến `--brand` đã đổi thành `#38b8a8` (sáng hơn) ở dark mode (dòng 35), nút `.primary` lại hardcode `#0f766e` (màu tối), khiến nút primary trong dark mode bị chìm, giảm tính "call-to-action".
    - Màu `--paper` trong dark mode là `#101a17`, nhưng background của body lại được set hardcode `linear-gradient(145deg, #0e1714, #1c1f12)` (dòng 36). Sự tồn tại song song biến `--paper` và gradient hardcode là thừa.
- **Khuyên cải thiện**: 
    - Nút `.primary` nên sử dụng `background: var(--brand)`. Nếu cần màu primary tối trong dark mode, hãy tạo riêng một token `var(--brand-solid)`.
    - Hạn chế hardcode màu trong selector dark mode, hãy override các biến `--var` ở block `:root` cho dark mode, các component sẽ tự nhận màu mới.

### Finding 6: Typography Responsive và Line-height
- **Vị trí**: Dòng 1, dòng 3
- **Mức độ**: Note
- **Mô tả**: Sử dụng `clamp(44px, 7vw, 82px)` (dòng 1) cho thẻ h1 là một practice tốt cho typography responsive. Tuy nhiên, line-height của đoạn văn bản dài `.lead` là 1.6, trong khi `.bubble` (tin nhắn chat) là 1.45 (dòng 3), điều này hợp lý (đoạn text dài cần line-height cao hơn text ngắn trong bubble). Tuy nhiên, không có token typography. Font size lẻ (`21px`, `17px`, `13px`) vẫn đang được sử dụng.
- **Khuyên cải thiện**: Chuẩn hóa typography scale (12px, 14px, 16px, 18px, 20px, 24px, v.v.).

### Finding 7: Breakpoint
- **Vị trí**: Dòng 18 (`@media(max-width:760px)`)
- **Mức độ**: Note
- **Mô tả**: Sử dụng breakpoint `760px` (có lẽ cho mobile/tablet portrait). Có thêm các breakpoint lẻ như `900px`, `1100px`, `800px`, `600px` rải rác trong file. Việc quản lý breakpoint phân tán như vậy sẽ khó maintain khi dự án lớn lên.
- **Khuyên cải thiện**: Gom nhóm breakpoint và sử dụng biến CSS nếu có thể (CSS Custom Properties không support dùng trực tiếp cho media query, nhưng có thể dùng CSS preprocessor như Sass, hoặc tổ chức lại vị trí code theo cụm logic).

---

## 3. Tổng kết (Summary)

Design system hiện tại mang lại cảm giác hiện đại, sạch sẽ với tone màu xanh Teal khá sang trọng, kết hợp tốt với hiệu ứng gradient nền và shadow lớn mềm mại ở light mode. Thẻ responsive typography (`clamp`) hoạt động hiệu quả. 

Tuy nhiên, cấu trúc CSS bộc lộ nhiều điểm yếu của việc "code chay" không qua design system chặt chẽ: Magic numbers xuất hiện dày đặc ở spacing (7px, 11px, 13px) và border-radius, tạo cảm giác thiếu tinh tế pixel-perfect. Bảng màu thiếu các shade/tint cơ bản (đặc biệt là màu cảnh báo/lỗi bị hardcode) và có sự vi phạm nhẹ về tương phản WCAG AA ở text màu `muted`. Dark mode được triển khai theo cách ghi đè trực tiếp các property thay vì token hóa, dẫn đến sự bất nhất (điển hình là nút Primary bị chìm trong dark mode do hardcode màu cũ). 

Cải thiện bằng cách thiết lập hệ thống token đầy đủ (spacing grid 4px, color scale, elevation) sẽ nâng tầm thẩm mỹ và độ chuyên nghiệp của dự án lên đáng kể.

**Độ tự tin (Confidence): 9/10** (Đã tính toán thủ công Luminance, phân tích trực tiếp class logic).