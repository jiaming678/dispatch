# 长久物流全国调度指挥中心

🚚 物流数据可视化大屏应用

## 技术栈

- 后端：Flask + Pandas
- 前端：HTML + CSS (暗黑科技风) + ECharts
- 地图：阿里云 DataV

## 运行方式

### 1. 安装依赖
```bash
pip install flask pandas
```

### 2. 放入数据
在 `路由池数据` 文件夹中放入 CSV 文件

### 3. 运行
```bash
python app.py
```

### 4. 访问
浏览器打开 http://localhost:5000

## 项目结构

```
长久物流大屏/
├── app.py              # Flask后端
├── templates/
│   └── index.html     # 前端页面
├── 路由池数据/          # CSV数据文件
└── .gitignore
```

## 功能

- 📊 历史路由资源库：热力图、饼图、柱状图
- 📡 实时运力调度大厅：大区分布、车队展示

## 作者

长久物流
