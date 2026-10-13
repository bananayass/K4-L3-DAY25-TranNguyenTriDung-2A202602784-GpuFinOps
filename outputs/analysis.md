# Phân tích GPU FinOps cho NimbusAI

## Chi phí trước và sau

Chi phí tháng giảm từ $27.133 xuống $15.137, tiết kiệm $11.996 (44,2%)

Chi phí inference giảm từ $6,488 xuống $1,126 trên mỗi triệu token, tương đương giảm 82,6%

Tổng savings là ước tính có điều kiện vì baseline chưa tính chi phí fleet M1 và dữ liệu chưa nối GPU với workload

Nếu fleet M1 là riêng, baseline khoảng $42.527 và tỷ lệ tiết kiệm còn 28,2%

## Đòn bẩy tiết kiệm

| Đòn bẩy | Tiết kiệm/tháng | Tỷ trọng |
|---|---:|---:|
| Spot/reserved | $10.040 | 83,7% |
| Inference: cascade/cache/batch | $1.212 | 10,1% |
| Tắt GPU nhàn rỗi | $600 | 5,0% |
| Right-sizing | $144 | 1,2% |

Spot/reserved tiết kiệm nhiều nhất vì các job chạy lâu có thể dùng GPU giá thấp hơn

Cascade tiết kiệm phần lớn chi phí inference vì 80% request chuyển sang model nhỏ hơn; cache và batch giảm thêm lần lượt $36 và $53,70 mỗi tháng

## GPU-Util Lie

`gpu-h100-4` có GPU-Util 98,2% nhưng MFU 0,194; `gpu-a10g-1` lần lượt là 96,9% và 0,268

GPU bận không có nghĩa là đang tính toán hiệu quả; chờ bộ nhớ, đồng bộ hoặc kernel nhỏ có thể làm throughput thấp

Nếu chạy đủ tháng theo giá on-demand, hai GPU này tốn lần lượt $1.800 và $720; đây là chi phí công suất có rủi ro lãng phí, chưa phải khoản tiết kiệm chắc chắn

`gpu-h100-5` bỏ không 8 giờ mỗi ngày, tốn trực tiếp khoảng $20/ngày hay $600/tháng

## Hai phần mở rộng

Right-sizing chuyển một GPU A10G (`gpu-a10g-0`) sang L4, tiết kiệm khoảng $144/tháng khi giữ đủ VRAM, băng thông và hiệu năng đã đo

Phần reasoning phân tích 201 request, tức 8,4% tổng số request và 16,5% token cùng chi phí; chi phí nhóm này khoảng $1,40/ngày

Mô hình ước tính reasoning dùng 29.787,74 Wh/ngày, chiếm 94% năng lượng; trên cùng số token, mức này cao gấp 80 lần traffic thường

Đây là ước tính điện, không phải số đo thực tế; toàn bộ request reasoning thuộc team eval nên chưa thể tách riêng nguyên nhân

## Điện năng và phát thải

Một truy vấn dùng khoảng 0,24 Wh và thải 0,091 gCO2e tại us-east-1

europe-north1 sạch carbon nhất; us-east-wa có điện rẻ nhất, nên chọn vùng theo ưu tiên về phát thải, giá GPU và độ trễ

## Ba việc nên làm trước

1. Chuyển job chịu gián đoạn sang spot và lưu checkpoint; chỉ dùng reserved khi đã rõ thời gian chạy
2. Chuyển request đơn giản sang model nhỏ, rồi dùng cache và batch khi độ trễ cho phép
3. Tắt GPU nhàn rỗi, thử right-size sau khi đo lại hiệu năng, rồi đối chiếu resource ID và tag trước khi chia hóa đơn
