# 更新日誌

> 本文件由簡體中文版經 OpenCC 簡繁轉換產生，用語以台灣習慣為準；內容如有差異，請以簡體中文版為準。

## v2026.9.26-beta
- 新增任務暫停/繼續功能，支援按鈕、全域性快捷鍵與遊戲內日誌懸浮窗狀態顯示
- 任務日誌區新增右鍵選單，支援複製/全選、清空日誌與開啟日誌資料夾
- 命令列支援列出與執行自定義流程
- Mirror 醬 CDK 卡片新增查詢天數按鈕
- 修復收藏狀態下無法識別角色緋櫻
- 修復無法切換到虛構敘事主介面
- 修復流程編排啟動的流程不切換到遊戲視窗
- 修復混沌回憶預設關卡範圍調整為 10-12
- 修復定時任務更新後未恢復托盤最小化狀態
- 最佳化效能和穩定性並修復若干已知問題
- [歡迎關注我們的B站賬號，獲取最新動態和教程](https://space.bilibili.com/3706960664857075)

## v2026.9.25
- 支援 Fate 聯動角色遠坂凜與吉爾伽美什
- 流程編排支援滑動滑鼠 [#1221](https://github.com/moesnow/March7thAssistant/pull/1221) @AnonMoi
- 定時任務支援新增流程編排
- 新增 Qmsg 醬 QQ 推送通知 [#1229](https://github.com/moesnow/March7thAssistant/pull/1229)
- 修復貨幣戰爭迴圈中的結算退出與開局確認 [#1223](https://github.com/moesnow/March7thAssistant/pull/1223) @LumiaBlack51
- 修復 SMTP 純文本模式下忽略截圖的問題 [#1217](https://github.com/moesnow/March7thAssistant/pull/1217) @23swccp
- 修復主頁卡片編輯器深色模式樣式不生效 [#1166](https://github.com/moesnow/March7thAssistant/pull/1166) @wha7ev9r
- 修復差分宇宙貪吃麵具最後區域選擇階段的確認彈窗
- 修復更新後未恢復托盤最小化狀態
- 修復配置檔案損壞時未備份導致配置丟失
- 修復貨幣戰爭雲遊戲保活、超時退出及敗局結算識別 [#1226](https://github.com/moesnow/March7thAssistant/pull/1226) @LumiaBlack51
- 修復 Docker 單檔案掛載時配置檔案無法儲存 [#1231](https://github.com/moesnow/March7thAssistant/pull/1231) @lingyezhixing
- 最佳化多語言翻譯，修正繁體用語並補全英日韓文案
- 最佳化效能和穩定性並修復若干已知問題

## v2026.9.7
- 修復貨幣戰爭入口互動異常 [#1209](https://github.com/moesnow/March7thAssistant/pull/1209) @LumiaBlack51
- 修復 OpenSSL 環境變數導致的啟動閃退
- 最佳化效能和穩定性並修復若干已知問題

## v2026.8.28
- 啟動遊戲前檢測遊戲是否已在執行 [#1189](https://github.com/moesnow/March7thAssistant/pull/1189) @girl-dream
- 郵件推送新增純文本模式 [#1173](https://github.com/moesnow/March7thAssistant/pull/1173)
- 修復自動對話失效 [#1191](https://github.com/moesnow/March7thAssistant/pull/1191) @FullError11
- 新增新曆戰餘響的掉落物識別 [#1188](https://github.com/moesnow/March7thAssistant/pull/1188) @shing-yu
- 防止雲遊戲無視窗模式鎖定系統滑鼠 [#1171](https://github.com/moesnow/March7thAssistant/pull/1171) @CisageX
- 修復定時任務非零退出碼時仍提示完成的問題 [#1176](https://github.com/moesnow/March7thAssistant/pull/1176) @yJader
- 支援差分宇宙人才管理階段介面 [#1193](https://github.com/moesnow/March7thAssistant/pull/1193) @DipsyHou
- 連續除錯埠不可用時由系統分配埠 [#1194](https://github.com/moesnow/March7thAssistant/pull/1194) @LumiaBlack51
- 最佳化成就獎勵領取流程 [#1155](https://github.com/moesnow/March7thAssistant/pull/1155) @sparklelcm333
- 移除無效和重複的依賴項 [#1183](https://github.com/moesnow/March7thAssistant/pull/1183) [#1184](https://github.com/moesnow/March7thAssistant/pull/1184) @ZardHju
- 最佳化效能和穩定性並修復若干已知問題

## v2026.7.26
- 新增 4.4 版本新增副本
- 同步 4.4 版本聯動卡池名稱改動
- 貨幣戰爭新增祈願試煉彈窗適配
- 貨幣戰爭新增選擇夥伴彈窗適配
- 貨幣戰爭支援連續多個彈窗按序處理
- 新增保留體力計劃選項 [#1140](https://github.com/moesnow/March7thAssistant/pull/1140) @henry3218
- 增加貨幣戰爭查詢難度1關卡的迴圈上限至100次
- 更新支援獎勵的圖示 [#1152](https://github.com/moesnow/March7thAssistant/pull/1152) @sparklelcm333
- 修復 pygetwindow 導致非 Windows 平臺啟動失敗 [#1127](https://github.com/moesnow/March7thAssistant/pull/1127) @zzy9001
- 最佳化掉落物彈窗識別邏輯並適配新版本 [#1146](https://github.com/moesnow/March7thAssistant/pull/1146) @shing-yu
- 修復 Chrome 啟動錯誤和嘗試自動遞增除錯埠 [#1144](https://github.com/moesnow/March7thAssistant/pull/1144) @CodingAQ
- 最佳化效能和穩定性並修復若干已知問題

## v2026.6.8
- 支援 4.3 新副本和角色 [#1109](https://github.com/moesnow/March7thAssistant/pull/1109) @shing-yu
- 新增自動對話全域性快捷鍵切換功能
- 支援處理稍後再看介面
- 為推送方式新增配置教程按鈕並最佳化排序
- 修復雲遊戲登入超時處理 [#1115](https://github.com/moesnow/March7thAssistant/pull/1115) @shing-yu
- 修復新開拓任務彈窗識別 [#1106](https://github.com/moesnow/March7thAssistant/pull/1106) @loader3229
- 修復編輯主頁卡片和流程編排彈窗的深色模式適配
- 修復混合 DPI 雙屏下獲取邏輯解析度而非物理解析度的問題
- 修復背包介面新增超時時的確認按鈕點選處理
- 修復存在紅點時無法正常切換到材料合成
- 最佳化效能和穩定性並修復若干已知問題

## v2026.5.27
- 支援開拓者·歡愉 [#1085](https://github.com/moesnow/March7thAssistant/pull/1085) @shing-yu
- 支援位面飾品提取自動切換隊伍 [#938](https://github.com/moesnow/March7thAssistant/pull/938) @alex3236
- 雲遊戲支援使用付費時長以及戰鬥超時處理 [#1051](https://github.com/moesnow/March7thAssistant/pull/1051) [#1059](https://github.com/moesnow/March7thAssistant/pull/1059) @shing-yu
- Telegram 推送支援 Topics 群組
- Bark 推送新增 base_url 引數支援自定義伺服器地址
- 企業微信應用通知新增自定義 URL 支援 [#1072](https://github.com/moesnow/March7thAssistant/pull/1072) @shing-yu
- 新增對自動切換視角彈窗的支援 [#1084](https://github.com/moesnow/March7thAssistant/pull/1084) @shing-yu
- 更新副本掉落配置，修復部分新副本無法識別的問題 [#1081](https://github.com/moesnow/March7thAssistant/pull/1081) @g60cBQ
- 最佳化貨幣戰爭裝備識別邏輯，阿格萊雅和希兒策略下支援識別進階裝備 [#1054](https://github.com/moesnow/March7thAssistant/pull/1054) @loader3229
- 修復模擬宇宙快速啟動實際執行型別和描述不一致
- 修復 CI 構建配置相容性問題 [#1065](https://github.com/moesnow/March7thAssistant/pull/1065) @sparklelcm333
- 最佳化效能和穩定性並修復若干已知問題

## v2026.5.12
- 貨幣戰爭新增 “希兒” 策略（測試版）
- 新增每月自動合成自塑塵脂、兌換專票通票等超值商品
- 支援主動完成每日實訓任務派遣委託
- 支援遐蝶皮膚「幽夢翩躚」 [#1048](https://github.com/moesnow/March7thAssistant/issues/1048) @shing-yu
- 幫助頁面樣式最佳化 [#1044](https://github.com/moesnow/March7thAssistant/issues/1044) @Because66666
- 修復歷戰餘響提前解鎖提示框影響識別 [#1047](https://github.com/moesnow/March7thAssistant/issues/1047) @shing-yu
- Linux/macOS 瀏覽器關閉邏輯最佳化 [#1033](https://github.com/moesnow/March7thAssistant/issues/1033) @shing-yu @stelahaveno
- 最佳化效能和穩定性並修復若干已知問題

## v2026.5.6
- 新增 “日常” 任務（合併每日實訓和體力）以及 “清體力” 總開關
- 新增 “定時任務” 支援鏈式啟動
- 新增 “流程編排” 支援新增終止流程步驟
- 新增 “除錯模式” 功能，支援在 Windows 上即時繪製檢測範圍框
- 新增支援修改開/關 “自動戰鬥” 的按鍵
- 優化了自動對話功能
- 優化了幫助頁面支援複製和自動換行 [#1035](https://github.com/moesnow/March7thAssistant/issues/1035) @Because66666
- 差分宇宙現在會記錄今日和每週的執行次數
- 修復了 “流程編排” 按下操作會自動鬆開以及不支援中文路徑模板圖片
- 修復遊戲已啟動時不會檢查解析度是否正確
- 最佳化效能和穩定性並修復若干已知問題

## v2026.5.1
- 新增 “流程編排” 功能，支援建立簡單的自動化流程
- 支援飾品提取和歷戰餘響連續挑戰 [#1014](https://github.com/moesnow/March7thAssistant/issues/1014) @CL4R3T
- 修復定時任務中的外部程式對 BetterGI 的支援 [#1011](https://github.com/moesnow/March7thAssistant/pull/1011) @Daydreamer114
- 優化了雲遊戲的截圖效能，提高了差分宇宙任務的穩定性
- 最佳化效能和穩定性並修復若干已知問題

## v2026.4.27
- 支援 4.2 新角色和副本
- 針對A840對阿格萊雅策略進行了最佳化
- 修復了貨幣戰爭的若干已知問題
- 更新了使用教程和常見問題適配當前版本
- 最佳化自動對話功能，提高穩定性，新增簡訊支援
- 培養目標支援當目標僅剩下遺器時改用自定義副本
- 新增活動熱點通知，包含剩餘天數和完成情況 [#1007](https://github.com/moesnow/March7thAssistant/pull/1007) @g60cBQ
- 更新程式支援命令列引數在最新版本時自動退出 [#1006](https://github.com/moesnow/March7thAssistant/pull/1006) @xinjiajuan
- 新增 uv 原始碼工作流 [#1003](https://github.com/moesnow/March7thAssistant/pull/1003) @Bot1822
- 修復無法正常進入活動和漫遊簽證介面
- 最佳化效能和穩定性並修復若干已知問題

## v2026.4.23
- 鋤大地（[Fhoe-Rail](https://github.com/linruowuyin/Fhoe-Rail/)）已經支援二相樂園啦~
- 貨幣戰爭新增“當前職級”選項
- 優化了差分宇宙事件關卡的處理邏輯
- 培養目標獲取新增 “掉落物識別” 方案，遇到異常時可嘗試切換 [#948](https://github.com/moesnow/March7thAssistant/pull/948) @g60cBQ
- 增加 OCR 模式配置，支援多種加速選項，並優化了記憶體佔用
- 修復因週期積分線將合併導致的差分宇宙異常
- 修復背包滿倉後會反覆嘗試分解遺器
- 修復無法正常進入 “郵件” 頁面
- 最佳化效能和穩定性並修復若干已知問題

## v2026.4.20
- 貨幣戰爭新增職級選擇
- 貨幣戰爭新增阿格萊雅策略
- 貨幣戰爭支援開拓者•記憶（需手動配置名稱）
- 現在差分宇宙在缺少隊伍時會自動嘗試選擇隊伍1
- 新增簡訊獎勵領取功能 [#964](https://github.com/moesnow/March7thAssistant/pull/964) @g60cBQ
- 新增更新支援手動配置代理
- 主頁新增編輯按鈕支援自定義卡片
- 新增命令列引數允許啟動時不立即執行 [#970](https://github.com/moesnow/March7thAssistant/pull/970) @sgpublic
- 修復部分文字OCR識別錯誤 [#966](https://github.com/moesnow/March7thAssistant/pull/966) [#988](https://github.com/moesnow/March7thAssistant/pull/988) @JackyTang1
- 最佳化執行時記憶體峰值佔用，減少發生記憶體溢位的情況
- 最佳化效能和穩定性並修復若干已知問題

## v2026.4.14
- 支援在遊戲內顯示日誌
- 差分宇宙支援事件型別關卡
- 差分宇宙支援自定義站點選擇優先順序
- 差分宇宙可選星階模式 [#953](https://github.com/moesnow/March7thAssistant/pull/953) @JackyTang1
- 圖形介面語言切換後支援熱過載&設定選項卡支援橫向滾動 [#962](https://github.com/moesnow/March7thAssistant/pull/962) @360NENZ
- 最佳化和修復差分宇宙若干已知問題
- 修復通過抽卡記錄複製連結後在小程式內無法使用
- 最佳化效能和穩定性並修復若干已知問題

## v2026.4.9
- 適配差分宇宙-樂園漫記
- 貨幣戰爭新增速通模式
- 適配貨幣戰爭 “專家邀請函” 彈窗
- 雲遊戲支援檢測剩餘時長 [#931](https://github.com/moesnow/March7thAssistant/pull/931) @awsl1110
- 自動切換隊伍支援所有預設編號 [#937](https://github.com/moesnow/March7thAssistant/pull/937) @Alex3236
- 最佳化和修復貨幣戰爭若干已知問題
- 最佳化和修復差分宇宙若干已知問題
- 圖形介面支援自定義記憶視窗大小或位置
- 最佳化效能和穩定性並修復若干已知問題

## v2026.3.25
- 支援 4.1 版本新增關卡
- 支援通知合併進行訊息推送
- 修復偶現無法正確跳過劇情
- 修復 bilibili 服無法正常進入遊戲
- 最佳化效能和穩定性並修復若干已知問題

## v2026.3.13
- 體力計劃和定時任務新增了排序功能
- 允許為特定的副本配置不同的出戰隊伍 [#913](https://github.com/moesnow/March7thAssistant/pull/913) @g60cBQ
- 推送通知的引數配置介面新增了詳細的文字描述
- 針對多顯示器環境和懸浮窗遮擋問題優化了截圖方式
- 最佳化效能和穩定性並修復若干已知問題

## v2026.3.7
- 支援爻光、火花、阮梅時裝 [#905](https://github.com/moesnow/March7thAssistant/pull/905) @0frostmourne0
- 更新差分宇宙配置選項現在預設停用 GPU 加速
- 修復特定條件下會重複觸發同一定時任務
- 修復設定遊戲路徑後側邊欄啟動遊戲按鈕不會即時生效
- 修復逐光撿金選擇角色時命途切換視窗阻礙後續流程 [#907](https://github.com/moesnow/March7thAssistant/pull/907) @g60cBQ
- 最佳化效能和穩定性並修復若干已知問題

## v2026.2.28
- 適配 4.0 版本貨幣戰爭新增投資環境
- 適配支援介面支援替換隊伍中已有角色 [#900](https://github.com/moesnow/March7thAssistant/pull/900) @g60cBQ
- 最佳化效能和穩定性並修復若干已知問題

## v2026.2.21
- 支援 4.0 版本新增關卡
- 適配 4.0 版本支援新介面 [#882](https://github.com/moesnow/March7thAssistant/pull/882) @g60cBQ
- 適配 4.0 版本委託獎勵新介面
- 適配 4.0 版本飾品提取編隊新介面 [#896](https://github.com/moesnow/March7thAssistant/pull/896) @g60cBQ
- 新增新版本本地化翻譯 [#883](https://github.com/moesnow/March7thAssistant/pull/883) @g60cBQ
- 補充一些遺漏的本地化翻譯 [#868](https://github.com/moesnow/March7thAssistant/pull/868) @loader3229
- 雲遊戲二維碼登入支援訊息推送 [#893](https://github.com/moesnow/March7thAssistant/pull/893) @architect9331
- 修復獲取抽卡記錄時請求出錯
- 修復貨幣戰爭補給階段選擇異常
- 修復培養目標無法正確識別擬造花萼金 [#888](https://github.com/moesnow/March7thAssistant/pull/888) @g60cBQ
- 修復非簡體中文語言修改副本型別後導致清體力出錯 [#881](https://github.com/moesnow/March7thAssistant/pull/881)
- 修復 macOS 通過 docker 執行時 OCR 識別異常 [#891](https://github.com/moesnow/March7thAssistant/issues/891)
- 修復系統睡眠或休眠後迴圈模式未按時執行的問題
- 最佳化效能和穩定性並修復若干已知問題

## v2026.2.9
- 支援中文格式的兌換碼
- 圖形介面支援多語言 [#856](https://github.com/moesnow/March7thAssistant/pull/856) @hohofught
- 新增支援三星光錐自動合成 [#854](https://github.com/moesnow/March7thAssistant/pull/854) @vintcessun
- 修復偶現獲取培養目標副本出錯 [#857](https://github.com/moesnow/March7thAssistant/pull/857) @g60cBQ
- 修正一些本地化翻譯錯誤 @loader3229 @g60cBQ @hohofught
- 最佳化效能和穩定性並修復若干已知問題

## v2026.1.21
- 支援貨幣戰爭領取積分獎勵後自動使用深度沉浸器
- 新增 MeoW 推送支援 [#850](https://github.com/moesnow/March7thAssistant/pull/850) @pboymt
- 最佳化效能和穩定性並修復若干已知問題
- 注意：因為 v2026.1.18 更新存在 bug，需要 [手動下載](https://github.com/moesnow/March7thAssistant/releases/tag/v2026.1.21) 覆蓋更新到新版本！！！
- [若已有 Mirror醬 CDK 可點此處高速下載](https://mirrorchyan.com/zh/download?rid=March7thAssistant&os=&arch=&channel=stable&source=m7a-release)

## v2026.1.19
- 對圖形介面進行了全面升級最佳化
- 新增啟動遊戲前自動檢測並開啟戰鬥二倍速功能
- 原始碼執行適配 macOS/Linux 並支援 [Docker 部署](https://m7a.top/#/assets/docs/Docker)
- 托盤右鍵選單新增設定選項
- 雲遊戲無視窗模式支援二維碼登入
- 雲遊戲排隊增加預計等待時間提示
- 升級 OCR 推理引擎和模型
- 最佳化 “未找到執行檔” 時的報錯資訊 [解決方法](https://m7a.top/#/assets/docs/FAQ)
- 修復培養計劃在沒有足夠資源時執行飾品提取
- 修復部分文字 OCR 識別異常
- 修復托盤區恢復時日誌視窗顯示異常空白
- 修復二維碼過期後無法正確重新整理 [#843](https://github.com/moesnow/March7thAssistant/pull/843) @eloay

## v2025.12.31
- 支援通過米哈遊啟動器自動更新遊戲（“設定→程式”內開啟）
- 定時任務支援新增通過啟動器預下載遊戲
- 現在同一路徑只會啟動一個圖形介面例項
- 修復更多文字 OCR 識別異常 [#828](https://github.com/moesnow/March7thAssistant/pull/828) @loader3229
- 修復雲遊戲不會選擇排隊佇列的問題 [#830](https://github.com/moesnow/March7thAssistant/pull/830) @loader3229
- 修復偶現無法正常切換程式視窗到前臺
- 修復切換主題後從托盤區恢復需要重新載入介面

## v2025.12.26
- 定時執行支援新增多個定時任務和外部程式
- 最佳化沒有找到任何兌換碼時的處理邏輯
- 調整雲遊戲設定項允許的最大排隊時間範圍
- 修復B服登入介面UI變化導致的啟動異常
- 修復部分情況下領取每日實訓獎勵誤報未完成 [#820](https://github.com/moesnow/March7thAssistant/pull/820) @g60cBQ
- 修復培養目標在未能識別副本的情況下仍繼續執行 [#819](https://github.com/moesnow/March7thAssistant/pull/819) @g60cBQ

## v2025.12.21
- 支援大麗花和三月七·冬去煦至 [#813](https://github.com/moesnow/March7thAssistant/pull/813) @loader3229
- 新增成就獎勵領取功能 [#811](https://github.com/moesnow/March7thAssistant/pull/811) @g60cBQ
- 新增自動獲取兌換碼並領取功能
- 恢復觸屏模式功能支援
- 最佳化定時執行任務的觸發邏輯
- 最佳化貨幣戰爭支援未結算對局處理
- 完整包現在內建雲遊戲專用瀏覽器 [#815](https://github.com/moesnow/March7thAssistant/pull/815) @Patrick16262
- 修復迴歸使用者無法正確識別活動頁面
- 修復特定情況下體力計劃錯誤判定無法執行
- 修復啟用培養計劃後副本連續挑戰次數錯誤
- 修復雲·星穹鐵道後臺執行時剪貼簿失效的問題 [#816](https://github.com/moesnow/March7thAssistant/pull/816) @Patrick16262
- 修復使用雲遊戲無法快速啟動鋤大地

## v2025.12.16
- 新增日誌介面並最佳化任務執行方式
- 圖形介面新增觸控滾動支援 [#799](https://github.com/moesnow/March7thAssistant/pull/799) @g60cBQ
- 圖形介面支援最小化到托盤
- 雲遊戲下載使用國內映象源加速 [#792](https://github.com/moesnow/March7thAssistant/pull/792) @Patrick16262
- 最佳化和修復雲遊戲若干問題 [#800](https://github.com/moesnow/March7thAssistant/pull/800) [#804](https://github.com/moesnow/March7thAssistant/pull/804) @Patrick16262
- 最佳化 WebHook 推送支援更多配置項
- 修復自動主題功能未正常執行
- 修復執行差分宇宙積分獎勵時類別選擇錯誤
- 修復語言非中文時日誌介面顯示異常

## v2025.12.13

- 支援體力計劃
- 設定介面最佳化
- 雙倍活動支援讀取培養計劃 [#751](https://github.com/moesnow/March7thAssistant/pull/751) @g60cBQ
- 現在判斷每日實訓完成後會立即領取獎勵
- 飾品提取未配置角色時自動選擇第一個隊伍 [#788](https://github.com/moesnow/March7thAssistant/pull/788) @g60cBQ
- 解鎖幀率和自動修改解析度功能適配國際服
- 配置檔案變化後自動過載圖形介面

## v2025.12.10

- 最佳化和修復貨幣戰爭若干問題
- 副本名稱和隊伍角色支援手動輸入和即時自動補全
- 支援通知級別配置（如僅推送錯誤通知）
- 推送通知前會對截圖進行壓縮減小體積
- 新增 KOOK、WebHook 推送支援
- 新增 Bark 推送加密支援
- 新增自動清理超過 30 天的日誌檔案

## v2025.12.8

- 支援貨幣戰爭
- 修復貨幣戰爭若干異常問題
- 抽卡記錄支援 UIGF 格式匯入和匯出
- 清體力前會傳送至任意錨點 [#760](https://github.com/moesnow/March7thAssistant/pull/760) @Xuan-cc
- 最佳化和修復雲遊戲若干問題 [#763](https://github.com/moesnow/March7thAssistant/pull/763) @Patrick16262
- 任務完成後新增支援關閉顯示器
- 清空抽卡記錄時增加二次確認彈窗
- 修復培養目標擬造花萼副本資訊提取失敗 [#764](https://github.com/moesnow/March7thAssistant/pull/764) @g60cBQ
- 修復任務完成後執行 ps1 指令碼失敗 [#759](https://github.com/moesnow/March7thAssistant/pull/759) @0frostmourne0

## v2025.12.1

- 支援雲·星穹鐵道 [#750](https://github.com/moesnow/March7thAssistant/pull/750)
- 支援根據培養目標動態選擇副本 [#751](https://github.com/moesnow/March7thAssistant/pull/751)
- 每日實訓現在會讀取任務完成情況並調整任務執行 [#753](https://github.com/moesnow/March7thAssistant/pull/753)
- 企業微信機器人推送方式支援傳送圖片 [#742](https://github.com/moesnow/March7thAssistant/pull/742)
- 修復特定情況逐光撿金無法正確選取角色 [#747](https://github.com/moesnow/March7thAssistant/pull/747)
- 修復任務完成後選擇指令碼時發生閃退
- 修復偶現無法正常終止遊戲程序
- 修復UI變化導致差分宇宙和模擬宇宙檢測自動戰鬥異常
- 最佳化完整執行時任務的執行順序
- 最佳化更新程式存在的一些問題
- 最佳化自動登入流程

## v2025.11.11

- 更新“優先執行一次差分宇宙”任務的週期為每兩週一次
- 使用SMTP傳送通知時支援不使用使用者名稱 [#730](https://github.com/moesnow/March7thAssistant/pull/730) [#738](https://github.com/moesnow/March7thAssistant/pull/738)
- 修復 3.7 新周本識別異常 [#728](https://github.com/moesnow/March7thAssistant/pull/728)
- 修復兌換碼入口識別異常 [#734](https://github.com/moesnow/March7thAssistant/pull/734)
- 修復特定條件下支援角色選擇介面點選異常

## v2025.11.6

- 支援 3.7 版本新增關卡和角色 [#725](https://github.com/moesnow/March7thAssistant/pull/725)
- 新增部分副本型別支援連續挑戰
- 重構自動對話工具增加配置選項並修復問題 [#720](https://github.com/moesnow/March7thAssistant/pull/720)
- 常見問題中新增多顯示器相關問題及解決方案
- 修復多賬號登入介面停滯問題 [#723](https://github.com/moesnow/March7thAssistant/pull/723)
- 修復前往模擬宇宙 UI 變化導致的異常
- 修復活動介面 UI 變化導致的異常
- 修復差分宇宙支援 UI 變化導致的異常
- 修復歷戰餘響執行日在設定介面顯示錯誤
- 圖形介面佈局最佳化

## v2025.10.15

- 支援 3.6 版本新增角色
- 最佳化自動登入過程並適配國際服 [#706](https://github.com/moesnow/March7thAssistant/pull/706)
- 支援隊伍中有角色死亡時繼續挑戰副本 [#705](https://github.com/moesnow/March7thAssistant/pull/705)
- 延遲部分超時時間最佳化機械硬碟使用體驗 [#701](https://github.com/moesnow/March7thAssistant/pull/701)
- 新增選項 “成功後暫停程式” 和 “失敗後直接退出” [#704](https://github.com/moesnow/March7thAssistant/pull/704) [#709](https://github.com/moesnow/March7thAssistant/pull/709)
- 修復部分使用者可能會出現的下載異常
- 最佳化下載程式支援自動使用系統代理
- 最佳化重置配置檔案功能的錯誤提示資訊

## v2025.9.25

- 支援 3.6 版本新增關卡和角色
- 最佳化日常“合成材料”的流程，且支援在設定中關閉
- 支援“支援列表”好友名稱留空，則僅查詢選擇的角色
- 修復配置支援角色“星期日”後偶現識別好友名稱異常
- 修復偶現“抽卡記錄”更新資料發生閃退
- 最佳化“在使用者登入時啟動”的選項說明
- 修正多個副本名稱識別錯誤

## v2025.9.10

- 支援 3.5 版本新增關卡和角色 [#687](https://github.com/moesnow/March7thAssistant/pull/687)
- 修正多個副本名稱識別錯誤
- 修復郵箱識別異常

## v2025.8.13

- 支援 3.5 版本新增關卡和角色 [#671](https://github.com/moesnow/March7thAssistant/pull/671)
- 修正多個副本名稱識別錯誤

## v2025.7.20

- 支援 Fate 聯動角色 [#640](https://github.com/moesnow/March7thAssistant/pull/640)
- 抽卡記錄支援聯動躍遷
- 新增支援地圖和躍遷的按鍵修改 [#635](https://github.com/moesnow/March7thAssistant/pull/635)
- “自動對話” 支援 “自動跳過對話” [#639](https://github.com/moesnow/March7thAssistant/pull/639)
- 多賬號管理功能支援清除登錄檔 [#636](https://github.com/moesnow/March7thAssistant/pull/636)
- 修復位面分裂活動導致的錯誤 [#643](https://github.com/moesnow/March7thAssistant/pull/643)
- 修復退出模擬宇宙導致的錯誤
- 修復自動對話不支援選項

## v2025.7.8

- 支援 3.4 版本新增關卡和角色 [#616](https://github.com/moesnow/March7thAssistant/pull/616)
- 修復無法正常進入 “溟簇之形” 副本

## v2025.6.14

- 支援 3.3 版本新增關卡和角色 [#580](https://github.com/moesnow/March7thAssistant/pull/580) [#597](https://github.com/moesnow/March7thAssistant/pull/597)
- 支援將抽卡記錄匯出為 Excel 檔案 [#574](https://github.com/moesnow/March7thAssistant/pull/574)
- 支援修改每輪擬造花萼挑戰次數 [#592](https://github.com/moesnow/March7thAssistant/pull/592)
- 設定頁面的滑塊增加按鈕以便更精細的控制 [#591](https://github.com/moesnow/March7thAssistant/pull/591)
- 修復差分宇宙暫退圖片 [#594](https://github.com/moesnow/March7thAssistant/pull/594)
- 修復抽卡資料存在異常時無法正常匯出 Excel
- 修復部分選項導致圖形介面閃退
- 修復 Gotify 推送異常
- 模擬宇宙（Auto_Simulated_Universe）v8.04
- 模擬宇宙支援通過 Mirror醬 進行更新

## v2025.4.18

- 適配二週年活動圖示
- 支援遐蝶 [#548](https://github.com/moesnow/March7thAssistant/pull/548)
- 支援配置從周幾後開始執行歷戰餘響（周本） [#479](https://github.com/moesnow/March7thAssistant/pull/479)
- 當遺器數量達到上限時，將會先執行分解四星遺器 [#524](https://github.com/moesnow/March7thAssistant/pull/524)
- OneBot 支援同時傳送私聊訊息和群訊息 [#540](https://github.com/moesnow/March7thAssistant/pull/540)
- 鋤大地增加翁法洛斯優先順序設定項 [#547](https://github.com/moesnow/March7thAssistant/pull/547)
- 最佳化 Mirror醬 使用體驗，增加CDK過期等錯誤提示
- 修復 飛書、Gotify、OneBot 推送 [#520](https://github.com/moesnow/March7thAssistant/pull/520) [#517](https://github.com/moesnow/March7thAssistant/pull/517)
- 修復未完成全部日常任務時可能無法正確領取獎勵
- 修復系統不支援自動主題時導致的閃退 [#525](https://github.com/moesnow/March7thAssistant/pull/525)
- 修復定時任務時間讀取本地區域設定導致的閃退 [#512](https://github.com/moesnow/March7thAssistant/pull/512)

## v2025.3.7

- 模擬宇宙（Auto_Simulated_Universe）適配新版本差分宇宙
- 支援 3.1 版本新增關卡和角色 [#486](https://github.com/moesnow/March7thAssistant/pull/486)
- 支援任務完成後執行指定程式或指令碼 [#453](https://github.com/moesnow/March7thAssistant/pull/453)
- 支援每週優先執行一次差分宇宙（設定-宇宙）
- 接入 Mirror醬 第三方應用分發平臺（關於 → 更新源）
- 修復設定培養目標後部分副本異常
- 修復無法進入經典模擬宇宙介面
- 修復無法正常合成消耗品 [#482](https://github.com/moesnow/March7thAssistant/issues/482)
- 觸屏模式暫不可用 [#487](https://github.com/moesnow/March7thAssistant/issues/487)

## v2025.1.20

- 支援 3.0 版本新增關卡和角色 [#442](https://github.com/moesnow/March7thAssistant/pull/442)
- 支援 “Matrix” 推送方式 [#440](https://github.com/moesnow/March7thAssistant/pull/440)
- 修改開拓力上限至300 [#447](https://github.com/moesnow/March7thAssistant/pull/447)
- 修復無法識別沉浸器數量 [#441](https://github.com/moesnow/March7thAssistant/issues/441)
- 修復無法更新抽卡記錄
- 部分程式碼規範性最佳化 [#443](https://github.com/moesnow/March7thAssistant/pull/443)

## v2024.12.18

### 更新
- "啟用位面分裂"開啟後，存在雙倍次數時體力優先「飾品提取」
- 支援在圖形介面中開關所有的推送方式，並修改對應的配置項
- 優化了“解鎖幀率”和“觸屏模式”的報錯提示（需要將遊戲影像質量修改為自定義）
- “啟用自動戰鬥檢測”開啟後，會在啟動遊戲前嘗試檢查並修改對應的登錄檔值

## v2024.12.12

### 更新
- 支援 “觸屏模式（雲遊戲移動端 UI）” 啟動遊戲（工具箱）
- “領取沉浸獎勵” 選項更改為 “領取沉浸獎勵/執行飾品提取”（領取積分獎勵後將自動執行飾品提取）
- 修復更換新桌布 “願今夜無夢” 後無法進入郵箱
- 修復無法識別並跳過末日幻影快速挑戰提示框 [#406](https://github.com/moesnow/March7thAssistant/issues/406) 

## v2.7.0

### 新功能
- 支援 “星期日” 、 “靈砂”
- 支援末日幻影 [#397](https://github.com/moesnow/March7thAssistant/pull/397) 
- 支援開機後自動執行（設定—雜項）
- 迴圈模式每次啟動前會重新載入配置檔案
- 增加 “在多顯示器上進行截圖” 選項（設定—雜項） [#392](https://github.com/moesnow/March7thAssistant/pull/392) 
- 支援自動獲取通過米哈遊啟動器安裝遊戲的路徑
- 最佳化主程式缺失後的報錯資訊

### 修復
- “日常任務” 會在每次啟動時被錯誤清空
- “自動對話” 狀態不會變化和速度過慢
- 降低角色頭像匹配閾值 [#356](https://github.com/moesnow/March7thAssistant/issues/356)

## v2.6.3

### 新功能
- 支援 2.6 版本新增關卡和角色（亂破）
- “副本名稱” 配置項支援手動輸入
- 陣亡導致挑戰失敗後支援自動重試 [#385](https://github.com/moesnow/March7thAssistant/pull/385)
- 支援自動批次使用兌換碼（工具箱）
- “抽卡記錄” 支援 “更新完整資料”（用於修復錯誤的抽卡資料）
- 迴圈模式支援 “根據開拓力”（原有模式） 和 “定時任務”（指定時間）
- 支援 “Server醬3” 推送方式 [#377](https://github.com/moesnow/March7thAssistant/pull/377)

### 修復
- 更換抽卡記錄 API
- 手動修改配置檔案會被圖形介面覆蓋 [#341](https://github.com/moesnow/March7thAssistant/issues/341) [#379](https://github.com/moesnow/March7thAssistant/issues/379)
- 遊戲視窗位於多顯示器副屏時截圖內容全黑或座標偏移 [#378](https://github.com/moesnow/March7thAssistant/pull/378) [#384](https://github.com/moesnow/March7thAssistant/pull/384)
- 暗黑主題下首次啟動程式後賬號列表背景色異常
- 存在“花藏繁生”活動但未啟用的情況下進入死迴圈

## v2.5.4

### 新功能
- 支援 2.5 版本新增關卡
- 支援功能重做（支援指定好友的指定角色且支援飾品提取使用，需重新配置）
- 支援 “翡翠” 、 “椒丘” 、“飛霄” 、 “貊澤”
- 支援B服啟動後自動點選 “登入” [#321](https://github.com/moesnow/March7thAssistant/discussions/321)
- “任務完成後” 新增 “重啟” 選項

### 修復
- 部分文字 OCR 識別異常
- 自動登入檢測異常 [#336](https://github.com/moesnow/March7thAssistant/issues/336)
- 支援功能在高分屏下異常 [#329](https://github.com/moesnow/March7thAssistant/issues/329)
- 修復擬造花萼（赤）錯行 [#328](https://github.com/moesnow/March7thAssistant/issues/328)
- 延長逐光撿金等待場景載入的時間 [#322](https://github.com/moesnow/March7thAssistant/issues/322)
- 最佳化飾品提取開始挑戰的邏輯 [#325](https://github.com/moesnow/March7thAssistant/issues/325)
- 最佳化 “啟動失敗” 的報錯提示

## v2.4.0

### 新功能
- 支援差分宇宙和飾品提取
- 支援 “智識之蕾•匹諾康尼大劇院” 關卡
- 支援 “雲璃” 、 “三月七（虛數）” 、 “開拓者（虛數）”
- 飛書 支援傳送截圖 [#310](https://github.com/moesnow/March7thAssistant/pull/310)

### 修復
- 新版材料合成頁面卡住的問題 [#231](https://github.com/moesnow/March7thAssistant/issues/231)

## v2.3.0

### 新功能
- 適配模擬宇宙新入口（需先解鎖差分宇宙）
- 支援 2.3 版本新增關卡 [#277](https://github.com/moesnow/March7thAssistant/pull/277)
- 支援B服 [#269](https://github.com/moesnow/March7thAssistant/pull/269)
- 支援國際服賬號操作 [#268](https://github.com/moesnow/March7thAssistant/pull/268)
- 支援逐光撿金和支援角色選擇 “流螢”
- 支援判斷米哈遊啟動器預設安裝路徑

### 修復
- 支援位於城市沙盤時正確進入地圖介面
- 混沌回憶重新整理後的彈窗有機率導致失敗
- PAC錯誤 [#276](https://github.com/moesnow/March7thAssistant/pull/276)

## v2.2.0

### 新功能
- 支援 2.2 版本新增關卡
- 支援逐光撿金和支援角色選擇 “砂金” 和 “知更鳥”
- 支援在設定配置模擬宇宙的命途和難度 [#223](https://github.com/moesnow/March7thAssistant/pull/223)
- 支援在設定配置鋤大地的購買選項 [#238](https://github.com/moesnow/March7thAssistant/pull/238)
- 設定內新增多賬戶管理功能 [#224](https://github.com/moesnow/March7thAssistant/pull/224)
- 支援登入過期時嘗試自動登入 [#237](https://github.com/moesnow/March7thAssistant/pull/237)
- 預設將模板圖片快取到記憶體中 [#244](https://github.com/moesnow/March7thAssistant/pull/244)
- 抽卡記錄新增 “清空” 按鈕
- 適配支援角色介面的新樣式

### 修復
- 無法切換到 “漫遊簽證” 和 “委託” 介面 [#247](https://github.com/moesnow/March7thAssistant/pull/247)
- 最新一期虛構敘事中部分角色開怪失敗 [#242](https://github.com/moesnow/March7thAssistant/pull/242)
- 無法領取 “支援” 和 “巡星之禮” 獎勵
- 特殊情況下抽卡記錄無法正常顯示和閃退

## v2.1.1

### 新功能
- 自動對話適配手柄介面 [#208](https://github.com/moesnow/March7thAssistant/pull/208)
- Telegram 推送方式支援配置代理或使用PAC [#219](https://github.com/moesnow/March7thAssistant/pull/219) [#222](https://github.com/moesnow/March7thAssistant/pull/222)
- 郵件推送方式支援 outlook [#220](https://github.com/moesnow/March7thAssistant/pull/220)

### 修復
- 原始碼執行鋤大地 [#211](https://github.com/moesnow/March7thAssistant/pull/211)
- 部分文字 OCR 識別異常

## v2.1.0

### 新功能
- 支援2.1新增副本和活動
- 委託獎勵更改為一鍵領取
- “擬造花萼（赤）”改為通過地點進行查詢
- 簽到活動開關合並
- 支援逐光撿金和支援角色選擇 “黃泉”和“加拉赫”

### 修復
- 紅點會導致逐光撿金判斷第二間失敗
- 合成任務因介面變化而無法完成
- “擬造花萼（赤）”向後相容

## v2.0.7

### 新功能
- 支援自定義訊息推送格式
- 混沌回憶檢測到角色陣亡自動重試
- 最佳化部分執行邏輯
- 完整執行結束推送剩餘開拓力和預計恢復時間（未開啟迴圈時） [#197](https://github.com/moesnow/March7thAssistant/pull/197)

### 修復
- 手機選單點選圖示異常

## v2.0.6

### 新功能
- 支援自定義每日合成沉浸器的個數 [#165](https://github.com/moesnow/March7thAssistant/pull/165)
- 新增快捷檢視日誌按鈕 [#150](https://github.com/moesnow/March7thAssistant/pull/150)
- 在 “完整執行” 清體力前增加一次 “委託獎勵檢測” [#171](https://github.com/moesnow/March7thAssistant/pull/171)

### 修復
- 降低查詢副本時的滾動速度
- 部分使用者報錯 “'cmd' 不是內部或外部命令...” 導致無法啟動遊戲
- 部分解析度全屏狀態判斷異常 [#183](https://github.com/moesnow/March7thAssistant/pull/183)

### 其他
- 主頁點選模擬宇宙快速啟動現在也會領取每週獎勵
- 移除設定內鋤大地和模擬宇宙更新等按鈕（請改從主頁執行相應功能）

## v2.0.5

### 新功能
- “任務完成後” 新增 “登出” 選項
- 工具箱新增幀率解鎖 [#161](https://github.com/moesnow/March7thAssistant/pull/161)
- “啟用自動修改解析度” 選項更改為 “啟用自動修改解析度並關閉自動 HDR” [#156](https://github.com/moesnow/March7thAssistant/pull/156)
- 新增 [OneBot](https://onebot.dev) 推送方式（QQ 機器人）
- 企業微信應用推送方式支援傳送圖片

### 修復
- 部分情況下解鎖幀率失敗
- 部分情況下無法正常傳送 gotify 通知
- 任務追蹤圖示導致地圖介面無法識別
- 多個紅點導致模擬宇宙領取每週獎勵失敗
- 快速解鎖教學動畫導致虛構敘事異常
- 主頁三月七背景在高縮放率下模糊的問題
- 某啟動器修改解析度登錄檔項後會導致登錄檔讀取錯誤

## v2.0.4

### 新功能
- 抽卡記錄匯出與簡單分析（支援 [SRGF](https://uigf.org/zh/standards/srgf.html) 資料格式匯入和匯出）
- 支援逐光撿金和支援角色選擇 “花火”

### 修復
- 特殊情況會導致下載失敗

## v2.0.3

### 新功能
- 支援所有手機桌布
- “自動劇情” 更名 “自動對話”
- 副本名稱新增 “無（跳過）” 選項
- 支援大於等於 1920*1080 的 16:9 解析度（實驗性功能）

### 修復
- 地圖介面判斷失敗
- “自動修改解析度” 失效
- 關閉 “啟用自動修改解析度” 選項會導致無法啟動遊戲

## v2.0.2

### 新功能
- 配隊介面最佳化
- 主頁部分模組支援多選項（鋤大地、模擬宇宙、逐光撿金）
- 支援重置鋤大地和模擬宇宙的配置檔案
- 新增 “遊戲重新整理時間”、“啟用自動修改解析度”、“啟用自動配置遊戲路徑” 選項
- 部分介面支援斷網重連

### 修復
- 支援識別3D地圖介面
- 適配混沌回憶重新整理後首次進入的新彈窗

## v2.0.1

### 新功能
- 新增遺器副本完成後“自動分解四星及以下遺器”功能（預設關閉）
- 新增“自動劇情”功能（側欄工具箱內開啟）
- 新增“啟動遊戲”按鈕（你可以將小助手當作啟動器來用了）
- 支援自動修改解析度，並在啟動遊戲後恢復原解析度
- 支援自定義推送方式 [#136](https://github.com/moesnow/March7thAssistant/pull/136)

### 修復
- 更新程式覆蓋失敗
- 異常狀態下歷戰餘響不會打滿3次
- 路徑中含有空格導致更新會跳轉到瀏覽器
- 更新程式會錯誤刪除 Fhoe-Rail\map 目錄（遇到此問題手動點一次單獨更新即可）

## v2.0.0

### 新功能
- 支援 2.0 版本新增關卡
- 支援 “限時提前解鎖” 關卡
- 支援選擇 “擬造花萼（金）偏好地區”
- 支援忘卻之庭和支援角色選擇 “真理醫生”、“黑天鵝”、“米沙”

### 修復
- 部分裝置 “焦炙之形” 關卡 OCR 識別異常
- 降低 “擬造花萼（赤）” 閾值要求
- “使用1次「萬能合成機」” 合成材料更改為 “微光原核”
- 版本更新後切換到 “回憶” 異常
- 版本更新後切換到 “逐光撿金” 異常
- 簽到活動讀取圖片失敗

## v1.7.7

### 新功能
- SMTP 支援傳送截圖 [#114](https://github.com/moesnow/March7thAssistant/pull/114)
- 支援 gotify 推送方式 [#112](https://github.com/moesnow/March7thAssistant/pull/112)
- 新增“啟用使用支援角色”選項（預設開啟） [#121](https://github.com/moesnow/March7thAssistant/issues/121)
- 修改“指定好友的支援角色”說明（填寫使用者名稱和UID都是支援的）

### 修復
- 遠端桌面多開會錯誤終止其他使用者的遊戲程序 [#113](https://github.com/moesnow/March7thAssistant/pull/113) [#35](https://github.com/moesnow/March7thAssistant/issues/35)
- 部分文字 OCR 識別異常（如 RapidOCR 的擬造花萼相關問題）
- 路徑中含有英文括號導致解壓失敗
- 模擬宇宙完成後無法正常領取獎勵

## v1.7.6

### 新功能
- 支援活動花藏繁生、異器盈界、位面分裂（預設關閉）

## v1.7.5

### 新功能
- 支援虛構敘事（預設關卡範圍 3-4）

## v1.7.4

### 新功能
- 支援更新時下載完整包（預設開啟，設定→關於）
- 支援加入預覽版更新渠道（設定→關於）
- 更新時支援呼叫 aria2 進行多執行緒下載（速度更快同時減少了下載中斷的情況）
- 更新時不再使用系統臨時目錄（方便新增防毒軟體白名單 [#86](https://github.com/moesnow/March7thAssistant/discussions/86#discussioncomment-7966897)）

### 修復
- 重複挑戰副本執行異常

## v1.7.3

### 新功能
- 支援忘卻之庭和支援角色選擇“銀枝”
- 支援關閉“啟用自動戰鬥檢測”（設定→按鍵）
- “自動戰鬥檢測”時間更改為無限制（臨時修復 [#96](https://github.com/moesnow/March7thAssistant/pull/96)）

### 修復
- 忘卻之庭交換隊伍後未交換秘技釋放順序
- 忘卻之庭挑戰失敗後會嘗試挑戰下一層

## v1.7.2

### 新功能
- 支援關閉每日實訓（可搭配每天一次模擬宇宙來完成500活躍度）
- 支援新曆戰餘響「蛀星的舊靨」
- 支援忘卻之庭和支援角色選擇“阮·梅”

### 修復
- 傳送忘卻之庭小機率錯誤點選成信用點圖示 [#91](https://github.com/moesnow/March7thAssistant/pull/91)

## v1.7.1


### 修復
- 鋤大地和模擬宇宙執行異常

## v1.7.0

### 新功能
- 適配每日實訓新任務
- 適配混沌回憶新介面（首次通關7層後需要手動完成教學動畫）
- 混沌回憶選角色介面支援滾動查詢
- 混沌回憶挑戰失敗後自動交換隊伍
- 混沌回憶預設關卡範圍更改為 7-12
- 支援的隊伍編號更改為 3-7
- 支援忘卻之庭和支援角色選擇“寒鴉”和“雪衣”
- 釘釘推送預設配置新增 secret 引數

### 修復
- 混沌回憶完成後領取獎勵失敗

## v1.6.9

### 新功能
- 適配混沌回憶1-5層更改為單個BOSS

### 修復
- 滾動後缺少延遲導致部分介面識別位置產生偏移（再一次）
- 移除部分測試程式碼

## v1.6.8


### 修復
- 模擬宇宙執行頻率配置名錯誤

## v1.6.7

### 新功能
- 支援開拓力優先合成沉浸器（預設關閉）
- 模擬宇宙支援修改執行頻率（預設每週一次）

### 修復
- 滾動後缺少延遲導致部分介面識別位置產生偏移

## v1.6.6

### 新功能
- 支援單獨執行“每日實訓”和“清體力”任務
- 更新 Fhoe-Rail 前會自動刪除舊的 map 資料夾

### 修復
- 自動儲存陣容導致“回憶”和“混沌回憶”無法正常執行
- 部分含生僻字的副本名稱小機率識別錯誤

## v1.6.5

### 新功能
- 支援使用整合模式執行模擬宇宙（預設）
- 支援忘卻之庭和支援角色選擇“託帕&賬賬”、“桂乃芬”和“藿藿”
- 新增副本“幽府之形”和“幽冥之徑”
- 支援擬造花萼體力小於60的情況 [#31](https://github.com/moesnow/March7thAssistant/pull/31)
- 支援從"開始選單"的快捷方式獲取遊戲路徑 [#29](https://github.com/moesnow/March7thAssistant/pull/29)

### 修復
- 自動從啟動器獲取遊戲路徑
- “使用消耗品”選中失敗後重試邏輯錯誤 [#41](https://github.com/moesnow/March7thAssistant/pull/41)

## v1.6.4

### 新功能
- 支援自定義模擬宇宙每週執行次數
- 支援完成“通關「模擬宇宙」（任意世界）的1個區域”
- 增加模擬宇宙完整性檢測 [#27](https://github.com/moesnow/March7thAssistant/pull/27)
- 支援“開拓者（穹）•毀滅”和“開拓者（穹）•存護” [#26](https://github.com/moesnow/March7thAssistant/pull/26)

### 修復
- 修復“遊戲退出失敗”的問題（回退實驗性改動）

## v1.6.3

### 新功能
- 支援通過“姬子試用”完成部分每日實訓（實驗性）
- 支援通過“回憶一”完成部分每日實訓（實驗性）
- Python 3.12.0 強力驅動
- 適配 Fhoe-Rail 的最新改動

### 修復
- “超時時間”修改為小數會導致圖形介面啟動崩潰
- 無法領取巡光之禮和巡星之禮最後一天的獎勵
### 其他
- 優化了現有功能的穩定性
- 現在只會停止當前使用者下的遊戲程序（實驗性）

## v1.6.2

### 新功能
- 支援使用“後備開拓力”和“燃料”
- 支援領取活動“巡光之禮”獎勵
- go-cqhttp 支援傳送截圖 [#21](https://github.com/moesnow/March7thAssistant/pull/21)

### 修復
- 有極小機率將開拓力識別成“米”字
### 其他
- 移除 power_total、dispatch_count、ocr_path 配置項
- 使用消耗品前會先篩選類別避免背包物品太多
- 升級 [PaddleOCR-json_v.1.3.1](https://github.com/hiroi-sora/PaddleOCR-json/releases/tag/v1.3.1)，相容 Win7 x64
- 支援 [RapidOCR-json_v0.2.0](https://github.com/hiroi-sora/RapidOCR-json/releases/download/v0.2.0/RapidOCR-json_v0.2.0.7z)，相容沒有 AVX 指令集的 CPU（自動判斷）

## v1.6.1

### 新功能
- 預設“副本名稱”（包含解釋）
- 支援“鏡流”和“開拓者（星）•毀滅”
- 支援領取活動“巡星之禮”獎勵
- 支援識別“開啟無名勳禮”介面

### 修復
- PushPlus推送 [#14](https://github.com/moesnow/March7thAssistant/pull/14)
### 其他
- 支援判斷手機桌布狀態
- 支援判斷是否購買了“無名客的榮勳”
- 配置隊伍改為從手機介面進入而不是按鍵

## v1.6.0

### 新功能
- 完成混沌回憶後自動領取星瓊獎勵
- 支援使用整合模式執行鋤大地（預設）
- 圖形介面新增測試訊息推送的功能
- 補全了大部分推送方式所需的配置項（推薦Bark、Server醬、郵箱Smtp）
- 支援從官方啟動器獲取遊戲路徑 [#10](https://github.com/moesnow/March7thAssistant/pull/10)

### 修復
- Windows終端高版本提示 “錯誤 2147942402 (0x80070002)” [#12](https://github.com/moesnow/March7thAssistant/pull/12)
- 低配置電腦檢測委託狀態偶爾異常
- 優化了 “發生錯誤: None” 的錯誤提示
- 開啟系統設定 “顯示強調色” 導致圖形介面顯示異常 [#11](https://github.com/moesnow/March7thAssistant/pull/11)
### 其他
- 使用多執行緒大大縮短了圖形介面的載入時間 [#11](https://github.com/moesnow/March7thAssistant/pull/11)
- 最佳化Python版本檢測和依賴安裝
- 內建“使用教程”，網頁版效果更佳

## v1.5.0

### 新功能
- 優化了“副本名稱”、“今日實訓”在圖形介面的顯示方式
- 嘗試支援國際服啟動介面（簡體中文）
- 合併 “退出遊戲”、“自動關機” 等功能為 “任務完成後”，預設 “無”
- 迴圈執行4點啟動現在會隨機延遲0-10分鐘執行

### 修復
- 更新時不會自動關閉圖形介面（檔案佔用導致更新失敗）
- 工作目錄不正確無法執行（常見於使用任務計劃程式）
### 其他
- 自動測速並選擇最快的映象源
- 現在“超時”功能可以正確強制停止“鋤大地”、“模擬宇宙”子任務
- 優先使用 Windows Terminal 而不是 conhost
- 棄用 “python_path”、“pip_mirror”、“github_mirror” 等設定項

## v1.4.2

### 新功能
- 內建 [Fhoe-Rail](https://github.com/linruowuyin/Fhoe-Rail) 自動鋤大地專案，支援在設定介面單獨更新，歡迎給作者點個 Star
- 調整了目錄結構，推薦手動進行本次更新，自動更新不會移除不再使用的檔案

## v1.4.1.1


### 修復
- 偶爾無法正常領取月卡
- 從環境變數自動獲取Python路徑失敗
- pushplus推送問題（再一次）

## v1.4.1

### 新功能
- 支援忘卻之庭和支援角色選擇“符玄”和“玲可”
- 增加選項用於開關實訓“完成1次「忘卻之庭」”（預設關閉）
- 支援任務完成後播放聲音提示（預設關閉）
- 支援Windows原生通知（預設開啟）
- 最佳化部分錯誤提示

### 修復
- 鋤大地原版啟動報錯
- pushplus推送問題

## v1.4.0

### 新功能
- 支援任務完成後自動關機（預設關閉）
- 圖形介面導航欄最佳化
- 圖形介面支援深色模式

### 修復
- 延長了點選傳送副本後的等待時間

## v1.3.5

### 新功能
- 支援圖形介面中修改秘技按鍵 [#4](https://github.com/moesnow/March7thAssistant/pull/4)
- 支援圖形介面中匯入配置檔案 [#4](https://github.com/moesnow/March7thAssistant/pull/4)
- 支援使用指定好友的支援角色 [#5](https://github.com/moesnow/March7thAssistant/pull/5)
- 下載過程支援顯示進度條

### 修復
- 更換手機桌布，導致委託檢測失敗

## v1.3.4.2

### 新功能
- 配置檔案中新增修改秘技按鍵 [#3](https://github.com/moesnow/March7thAssistant/pull/3)

### 修復
- 位面分裂活動橫幅導致無法自動進入黑塔辦公室
- 在圖形介面中隱藏“副本所需開拓力”設定項避免誤修改
- 嘗試解決卡在日常任務“完成1次「忘卻之庭」”的問題
- 嘗試解決自動戰鬥未自動開啟的問題

## v1.3.4.1


### 修復
- 修改 powershell 命令改用 cmd 執行
- 自動安裝 Python 的一些問題，現在可以正常安裝（實驗性）

## v1.3.4

### 新功能
- 支援忘卻之庭和支援角色選擇 “丹恆•飲月”
- 支援在設定中開啟模擬宇宙和鋤大地的原版圖形介面（用於設定命途等）
- 支援自動下載安裝 Python、PaddleOCR-json （實驗性）
- 最佳化三月七小助手和模擬宇宙的更新功能（實驗性）

### 修復
- 非4K解析度下視窗運行遊戲導致功能異常

## v1.3.3.1

### 新功能
- 支援在遊戲啟動後自動檢測並儲存遊戲路徑
- 更新常見問題（FQA）

## v1.3.3

### 新功能
- 支援設定是否領取無名勳禮獎勵（預設關閉）
- 添加了更多的錯誤檢測
- 更新常見問題（FQA）

## v1.3.2

### 新功能
- 支援自動開啟“自動戰鬥”
- 支援識別鋤大地和模擬宇宙執行狀態
- 支援識別遊戲更新所導致的需要重啟
- 支援在官方啟動器開啟的情況下啟動遊戲
- 鋤大地和模擬宇宙的指令碼遇到錯誤現在會立即終止

### 修復
- 執行任務後且圖形介面未關閉，修改配置會導致時間和日常狀態被覆蓋
- 啟動遊戲後未處於主介面判定啟動失敗（現支援任意已知介面）

## v1.3.1

### 新功能
- 支援模擬宇宙“領取沉浸獎勵”，在設定中開啟，預設關閉
- 支援單獨更新模擬宇宙版本（實驗性）
- 圖形介面支援自動更新版本（實驗性）
- 圖形介面支援手動檢測更新
- 圖形介面增加“更新日誌”、“常見問題”等子頁面

### 修復
- 最佳化模擬宇宙完成後的通知截圖

## v1.3.0.2

### 新功能
- 恢復 v1.3.0 中移除的使用支援角色（borrow_character_enable）選項
- 副本名稱設定為"無"代表即使有對應的實訓任務也不會去完成

### 修復
- v1.3.0 混沌回憶星數檢測異常

## v1.3.0.1


### 修復
- v1.3.0 通過圖形介面生成的配置檔案不正確

## v1.3.0

### 新功能
- 支援識別每日實訓內容並嘗試完成，而不是全部做一遍 [點選檢視支援任務](https://github.com/moesnow/March7thAssistant#%E6%AF%8F%E6%97%A5%E5%AE%9E%E8%AE%AD)
- 新增選項每週優先完成三次「歷戰餘響」（預設關閉）
- 副本名稱（instance_names）更改為根據副本型別單獨設定，同時也會用於“完成1次xxx”的實訓任務中
- 移除“使用支援角色”、“強制使用支援角色”、“啟用每日拍照”和“啟用每日合成/使用 材料/消耗品”配置選項
- 每週模擬宇宙執行前先檢查一遍可領取的獎勵

### 修復
- 嘗試解決低機率下識別副本名稱失敗
- 徹底解決每日實訓是否全部完成檢測不可信

## v1.2.6

### 新功能
- 支援更多副本型別：侵蝕隧洞、凝滯虛影、擬造花萼（金）、擬造花萼（赤）
- 設定中的捕獲截圖功能支援OCR識別文字，可用於複製副本名稱

## v1.2.5

### 新功能
- 內建鋤大地命令


### 修復
- 開拓力偶爾識別成“1240”而不是“/240”
- 每日實訓是否全部完成檢測失敗

## v1.2.4

### 新功能
- 圖形介面支援顯示更新日誌
- 更新模擬宇宙 [Auto_Simulated_Universe  v5.30](https://github.com/CHNZYX/Auto_Simulated_Universe/tree/f17c5db33a42d7f6e6204cb3e6e83ec2fd208e5e)


### 修復
- 1.3版本的各種UI變化導致的異常

## v1.2.3

### 新功能
- 混沌回憶支援檢測每關星數
- 副本名稱支援簡寫，例如【睿治之徑】


### 修復
- 偶爾點選速度過快導致領取實訓獎勵失敗
- 滑鼠位於螢幕左上角觸發安全策略導致點選失效
- 偶爾介面切換速度太慢導致消耗品識別點選位置偏移
- 檢測無名勳禮獎勵模板圖片錯誤
- 降低部分閾值要求，提高操作成功率
- 移除部分多餘的介面檢測，提高速度

## v1.2.2

### Features
- feat: add Bailu and Kafka
適配白露和卡芙卡
- feat: forgottenhall support melee character
混沌回憶支援近戰角色開怪
- feat: add take_screenshot to gui
圖形介面設定中新增捕獲截圖功能
- feat: add check update to gui
圖形介面啟動時檢測更新
- feat: add tip when start

### Fixes
- fix: use consumables when repeat
消耗品效果未過期導致無法使用
- fix: check_update option not available
更新檢測開關不可用
- fix: avoid trailblaze_power overflow
模擬宇宙前後清一次體力避免溢位
- fix: space cause text ocr fail
偶爾會識別出空格導致判斷文字失敗
- fix: exit function

## v1.2.1

### Features
- feat: auto change team
在打副本和鋤大地前可以自動切換隊伍
- feat: add submodule Auto_Simulated_Universe
新增模擬宇宙子模組

### Fixes
- fix: switch window problem
遊戲視窗偶爾無法切換到前臺
- fix: same borrow character
支援角色和原隊伍角色相同

## v1.2.0

### Features
- feat: graphical user interface
增加圖形使用者介面
