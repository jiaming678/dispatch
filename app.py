# -*- coding: utf-8 -*-
"""
长久物流全国调度指挥中心 - Flask后端
"""

from flask import Flask, render_template, jsonify, request
import pandas as pd
import os
import re

app = Flask(__name__)

# 全局数据
GLOBAL_DF = None
DATA_FILES = []

# ==================== 数据处理 ====================

def clean_province_name(name):
    """清理省份名称"""
    if pd.isna(name) or not name:
        return "未知"
    name = str(name).strip()
    # 去掉省市自治区等后缀
    name = re.sub(r'省|市|自治区|回族自治区|维吾尔自治区|壮族自治区', '', name)
    return name if name else "未知"

def ensure_native_type(value):
    """确保Python原生类型"""
    if pd.isna(value):
        return 0
    try:
        return int(value)
    except:
        try:
            return float(value)
        except:
            return 0

def load_data():
    """加载CSV数据"""
    global GLOBAL_DF, DATA_FILES
    
    # 获取当前目录
    current_dir = os.path.dirname(os.path.abspath(__file__)) if __name__ != "__main__" else os.getcwd()
    data_folder = os.path.join(current_dir, "路由池数据")
    
    print(f"📂 数据文件夹: {data_folder}")
    
    if not os.path.exists(data_folder):
        os.makedirs(data_folder)
        print("⚠️ 已创建空的 数据文件夹，请放入CSV文件")
        return
    
    csv_files = [f for f in os.listdir(data_folder) if f.endswith('.csv')]
    print(f"📄 找到 {len(csv_files)} 个CSV文件: {csv_files}")
    
    if not csv_files:
        print("⚠️ 未找到CSV文件")
        return
    
    dfs = []
    for f in csv_files:
        file_path = os.path.join(data_folder, f)
        print(f"📖 读取: {f}")
        try:
            df = pd.read_csv(file_path, encoding='utf-8-sig')
            print(f"   → 成功 {len(df)} 行, 列: {list(df.columns)[:5]}...")
            dfs.append(df)
        except Exception as e:
            print(f"   → 失败: {e}")
            try:
                df = pd.read_csv(file_path, encoding='gbk')
                dfs.append(df)
            except:
                print(f"   → GBK也失败")
    
    if not dfs:
        print("⚠️ 没有成功读取任何文件")
        return
    
    GLOBAL_DF = pd.concat(dfs, ignore_index=True)
    print(f"✅ 合并后共 {len(GLOBAL_DF)} 行数据")
    
    # 数据预处理 - 动态匹配列名
    cols = GLOBAL_DF.columns.tolist()
    print(f"📋 所有列名: {cols}")
    
    # 始发省
    origin_col = next((c for c in cols if '始发省' in c), None)
    if origin_col:
        GLOBAL_DF['始发省_清理'] = GLOBAL_DF[origin_col].apply(clean_province_name)
        print(f"🗺️ 始发省数据样本: {GLOBAL_DF['始发省_清理'].value_counts().head(5).to_dict()}")
    
    # 目的省
    dest_col = next((c for c in cols if '目的省' in c), None)
    if dest_col:
        GLOBAL_DF['目的省_清理'] = GLOBAL_DF[dest_col].apply(clean_province_name)
    
    # 品牌
    brand_col = next((c for c in cols if '品牌' in c), None)
    if brand_col:
        GLOBAL_DF['品牌_copy'] = GLOBAL_DF[brand_col].fillna('未知')
        print(f"🏭 品牌数据样本: {GLOBAL_DF['品牌_copy'].value_counts().head(5).to_dict()}")
    
    # 承运商类型
    carrier_col = next((c for c in cols if '承运商类型' in c), None)
    if carrier_col:
        GLOBAL_DF['运力类型'] = GLOBAL_DF[carrier_col].apply(
            lambda x: '自营' if '自营' in str(x) else '外协'
        )
        print(f"🚚 运力类型: {GLOBAL_DF['运力类型'].value_counts().to_dict()}")
    
    # 发车时间
    time_col = next((c for c in cols if '发车时间' in c), None)
    if time_col:
        try:
            GLOBAL_DF['发车时间_解析'] = pd.to_datetime(GLOBAL_DF[time_col], errors='coerce')
            print(f"📅 时间范围: {GLOBAL_DF['发车时间_解析'].min()} ~ {GLOBAL_DF['发车时间_解析'].max()}")
        except:
            pass
    
    DATA_FILES = csv_files

# ==================== API ====================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status')
def api_status():
    if GLOBAL_DF is None or GLOBAL_DF.empty:
        return jsonify({"status": "no_data", "message": "请在 路由池数据 文件夹中放入CSV文件"})
    
    return jsonify({
        "status": "ok",
        "total_rows": int(len(GLOBAL_DF)),
        "files": DATA_FILES
    })

def apply_filters(df, province, carrier_type, brand):
    """应用筛选条件"""
    if df is None or df.empty:
        return df
    
    # 省份筛选
    if province and province != '全国概览' and '始发省_清理' in df.columns:
        df = df[df['始发省_清理'] == province]
    
    # 承运商类型筛选
    if carrier_type and carrier_type != '全部' and '运力类型' in df.columns:
        df = df[df['运力类型'] == carrier_type]
    
    # 品牌筛选
    if brand and brand != '' and '品牌_copy' in df.columns:
        df = df[df['品牌_copy'] == brand]
    
    return df

@app.route('/api/kpi')
def api_kpi():
    if GLOBAL_DF is None or GLOBAL_DF.empty:
        return jsonify({"error": "无数据"})
    
    province = request.args.get('province', '全国概览')
    carrier_type = request.args.get('carrier_type', '全部')
    brand = request.args.get('brand', '')
    
    df = apply_filters(GLOBAL_DF.copy(), province, carrier_type, brand)
    
    total = ensure_native_type(len(df))
    national_total = ensure_native_type(len(GLOBAL_DF))
    
    # 运力统计
    self_op = 0
    outsource = 0
    if '运力类型' in df.columns:
        stats = df.groupby('运力类型').size()
        self_op = ensure_native_type(stats.get('自营', 0))
        outsource = ensure_native_type(stats.get('外协', 0))
    
    return jsonify({
        "total": total,
        "total_ratio": round(total / national_total * 100, 1) if national_total > 0 else 0,
        "self_ratio": round(self_op / total * 100, 1) if total > 0 else 0,
        "out_ratio": round(outsource / total * 100, 1) if total > 0 else 0
    })

@app.route('/api/map_data')
def api_map_data():
    """地图数据 - 支持两种模式：始发省分布 或 目的省流向"""
    if GLOBAL_DF is None or GLOBAL_DF.empty:
        return jsonify({"error": "无数据"})
    
    province = request.args.get('province', '全国概览')
    carrier_type = request.args.get('carrier_type', '全部')
    brand = request.args.get('brand', '')
    
    df = apply_filters(GLOBAL_DF.copy(), province, carrier_type, brand)
    
    if province and province != '全国概览' and '始发省_清理' in df.columns:
        # 选择某省份后，显示目的省流向
        if '目的省_清理' in df.columns:
            stats = df.groupby('目的省_清理').size()
            map_data = []
            for p, count in stats.items():
                name = p + "省" if p not in ["北京", "天津", "上海", "重庆"] else p + "市"
                map_data.append({"name": name, "value": ensure_native_type(count)})
            return jsonify(map_data)
    
    # 全国概览：显示始发省分布
    if '始发省_清理' in df.columns:
        stats = df.groupby('始发省_清理').size()
        map_data = []
        for p, count in stats.items():
            name = p + "省" if p not in ["北京", "天津", "上海", "重庆"] else p + "市"
            map_data.append({"name": name, "value": ensure_native_type(count)})
        return jsonify(map_data)
    
    return jsonify([])

@app.route('/api/carrier_data')
def api_carrier_data():
    if GLOBAL_DF is None or GLOBAL_DF.empty:
        return jsonify([])
    
    province = request.args.get('province', '全国概览')
    carrier_type = request.args.get('carrier_type', '全部')
    brand = request.args.get('brand', '')
    
    df = apply_filters(GLOBAL_DF.copy(), province, carrier_type, brand)
    
    result = []
    if '运力类型' in df.columns:
        stats = df.groupby('运力类型').size()
        for t, count in stats.items():
            result.append({"name": t, "value": ensure_native_type(count)})
    
    return jsonify(result if result else [{"name": "无数据", "value": 1}])

@app.route('/api/brand_data')
def api_brand_data():
    if GLOBAL_DF is None or GLOBAL_DF.empty:
        return jsonify([])
    
    province = request.args.get('province', '全国概览')
    carrier_type = request.args.get('carrier_type', '全部')
    brand = request.args.get('brand', '')
    
    df = apply_filters(GLOBAL_DF.copy(), province, carrier_type, brand)
    
    result = []
    if '品牌_copy' in df.columns:
        stats = df.groupby('品牌_copy').size().sort_values(ascending=False).head(10)
        for b, count in stats.items():
            result.append({"name": str(b), "value": ensure_native_type(count)})
    
    return jsonify(result[::-1])

@app.route('/api/dest_data')
def api_dest_data():
    if GLOBAL_DF is None or GLOBAL_DF.empty:
        return jsonify([])
    
    province = request.args.get('province', '全国概览')
    carrier_type = request.args.get('carrier_type', '全部')
    brand = request.args.get('brand', '')
    
    df = apply_filters(GLOBAL_DF.copy(), province, carrier_type, brand)
    
    result = []
    if '目的省_清理' in df.columns:
        stats = df.groupby('目的省_清理').size().sort_values(ascending=False).head(10)
        for dest, count in stats.items():
            result.append({"name": str(dest), "value": ensure_native_type(count)})
    
    return jsonify(result[::-1])

@app.route('/api/provinces')
def api_provinces():
    provinces = ["全国概览"]
    if GLOBAL_DF is not None and '始发省_清理' in GLOBAL_DF.columns:
        unique = GLOBAL_DF['始发省_清理'].unique().tolist()
        provinces.extend(sorted([p for p in unique if p and str(p) != '未知']))
    return jsonify(provinces)

@app.route('/api/date_range')
def api_date_range():
    if GLOBAL_DF is None or '发车时间_解析' not in GLOBAL_DF.columns:
        return jsonify({"min": None, "max": None})
    
    try:
        min_date = GLOBAL_DF['发车时间_解析'].min()
        max_date = GLOBAL_DF['发车时间_解析'].max()
        return jsonify({
            "min": min_date.strftime('%Y-%m-%d') if pd.notna(min_date) else None,
            "max": max_date.strftime('%Y-%m-%d') if pd.notna(max_date) else None
        })
    except:
        return jsonify({"min": None, "max": None})

# ==================== 启动 ====================

if __name__ == "__main__":
    print("=" * 50)
    print("🚚 长久物流全国调度指挥中心")
    print("=" * 50)
    load_data()
    print("🌐 启动服务: http://localhost:5000")
    print("=" * 50)
    app.run(debug=True, host='0.0.0.0', port=5000)
