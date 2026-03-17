#!/usr/bin/env python3
"""
整车物流调度分析 - Agent执行逻辑
Logistics Analysis Agent for Vehicle Fleet Management
"""

import os
import sys
import json
import argparse
from pathlib import Path
from collections import Counter, defaultdict

# 尝试导入必要的库
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

try:
    from openpyxl import load_workbook
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False


class LogisticsAnalyzer:
    """整车物流数据分析器"""
    
    def __init__(self, data_file):
        self.file = data_file
        self.data = None
        self.df = None
        
    def load_data(self):
        """加载数据"""
        if not os.path.exists(self.file):
            return False, f"文件不存在: {self.file}"
        
        ext = Path(self.file).suffix.lower()
        
        try:
            if ext in ['.xlsx', '.xls']:
                if not HAS_PANDAS:
                    # 使用内置解析器
                    return self._load_excel_native()
                self.df = pd.read_excel(self.file, sheet_name=0)
            elif ext == '.csv':
                if not HAS_PANDAS:
                    return self._load_csv_native()
                self.df = pd.read_csv(self.file, encoding='utf-8')
            else:
                return False, f"不支持的文件格式: {ext}"
            
            self.data = self.df.to_dict('records')
            return True, f"成功加载 {len(self.data)} 条数据"
            
        except Exception as e:
            return False, f"加载失败: {str(e)}"
    
    def _load_excel_native(self):
        """使用内置方式解析Excel（无pandas）"""
        import zipfile
        import xml.etree.ElementTree as ET
        
        def col_to_letter(n):
            result = ""
            while n >= 0:
                result = chr(65 + (n % 26)) + result
                n = n // 26 - 1
            return result
        
        with zipfile.ZipFile(self.file, 'r') as z:
            # 读取sharedStrings
            ss_xml = z.read('xl/sharedStrings.xml').decode('utf-8')
            root = ET.fromstring(ss_xml)
            ns = {'main': root.tag[1:root.tag.index('}')] if '}' in root.tag else ''}
            
            shared_strings = []
            for si in root.findall('.//{%s}si' % ns['main']):
                texts = []
                for t in si.findall('.//{%s}t' % ns['main']):
                    if t.text:
                        texts.append(t.text)
                shared_strings.append(''.join(texts))
            
            # 读取sheet1
            sheet_xml = z.read('xl/worksheets/sheet1.xml').decode('utf-8')
            sheet_root = ET.fromstring(sheet_xml)
            sheet_ns = {'main': sheet_root.tag[1:sheet_root.tag.index('}')] if '}' in sheet_root.tag else ''}
            
            sheet_data = sheet_root.find('.//{%s}sheetData' % sheet_ns['main'])
            if sheet_data is None:
                return False, "无法读取Sheet数据"
            
            rows = []
            headers = []
            
            for row in sheet_data.findall('{%s}row' % sheet_ns['main']):
                row_num = int(row.get('r', 0))
                cells = {}
                max_col = 0
                
                for cell in row.findall('{%s}c' % sheet_ns['main']):
                    cell_ref = cell.get('r')
                    cell_type = cell.get('t')
                    
                    v = cell.find('{%s}v' % sheet_ns['main'])
                    if v is not None and v.text:
                        val = v.text
                        if cell_type == 's':
                            try:
                                idx = int(val)
                                val = shared_strings[idx] if idx < len(shared_strings) else ''
                            except:
                                pass
                        cells[cell_ref] = val
                    else:
                        inline_str = cell.find('{%s}is' % sheet_ns['main'])
                        if inline_str is not None:
                            t = inline_str.find('{%s}t' % sheet_ns['main'])
                            if t is not None and t.text:
                                cells[cell_ref] = t.text
                        else:
                            cells[cell_ref] = ''
                    
                    if cell_ref:
                        col = ''.join(c for c in cell_ref if c.isalpha())
                        col_num = 0
                        for c in col:
                            col_num = col_num * 26 + (ord(c) - ord('A') + 1)
                        max_col = max(max_col, col_num)
                
                row_list = []
                for col in range(1, max_col + 1):
                    col_letter = col_to_letter(col - 1)
                    ref = f'{col_letter}{row_num}'
                    row_list.append(cells.get(ref, ''))
                
                if row_num == 1:
                    headers = row_list
                else:
                    rows.append(row_list)
            
            # 转换为字典列表
            self.data = []
            for row in rows:
                record = {}
                for i, h in enumerate(headers):
                    if i < len(row):
                        record[h] = row[i]
                self.data.append(record)
            
            return True, f"成功加载 {len(self.data)} 条数据"
    
    def _load_csv_native(self):
        """使用内置方式解析CSV"""
        import csv
        
        with open(self.file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows = list(reader)
        
        if len(rows) < 2:
            return False, "CSV文件为空"
        
        headers = rows[0]
        self.data = []
        
        for row in rows[1:]:
            record = {}
            for i, h in enumerate(headers):
                if i < len(row):
                    record[h] = row[i]
            self.data.append(record)
        
        return True, f"成功加载 {len(self.data)} 条数据"
    
    def analyze(self):
        """执行分析"""
        if not self.data:
            return {"error": "请先加载数据"}
        
        # 统计各项指标
        carrier_count = Counter()
        province_count = Counter()
        brand_count = Counter()
        route_count = Counter()
        region_count = Counter()
        
        for row in self.data:
            carrier = row.get('承运商名称', row.get('车队', ''))
            province = row.get('省公司', row.get('业务中心', ''))
            brand = row.get('品牌', '')
            from_prov = row.get('始发省', '')
            to_prov = row.get('目的省', '')
            region = row.get('大区', '')
            
            if carrier: carrier_count[carrier] += 1
            if province: province_count[province] += 1
            if brand: brand_count[brand] += 1
            if from_prov and to_prov: route_count[f"{from_prov}→{to_prov}"] += 1
            if region: region_count[region] += 1
        
        return {
            "total_orders": len(self.data),
            "carriers": dict(carrier_count.most_common(20)),
            "provinces": dict(province_count.most_common(20)),
            "brands": dict(brand_count.most_common(20)),
            "top_routes": dict(route_count.most_common(15)),
            "regions": dict(region_count)
        }
    
    def get_balance_report(self):
        """生成供需平衡表"""
        if not self.data:
            return {"error": "请先加载数据"}
        
        # 统计各车队业务量
        carrier_stats = defaultdict(lambda: {"total": 0, "routes": set(), "brands": set()})
        
        for row in self.data:
            carrier = row.get('承运商名称', '')
            from_prov = row.get('始发省', '')
            to_prov = row.get('目的省', '')
            brand = row.get('品牌', '')
            
            if carrier:
                carrier_stats[carrier]["total"] += 1
                if from_prov and to_prov:
                    carrier_stats[carrier]["routes"].add(f"{from_prov}→{to_prov}")
                if brand:
                    carrier_stats[carrier]["brands"].add(brand)
        
        # 转换为列表并排序
        result = []
        for carrier, stats in carrier_stats.items():
            result.append({
                "车队": carrier,
                "运单数": stats["total"],
                "线路数": len(stats["routes"]),
                "品牌数": len(stats["brands"]),
                "平均每线运单": round(stats["total"] / max(len(stats["routes"]), 1), 1)
            })
        
        result.sort(key=lambda x: x["运单数"], reverse=True)
        
        return {
            "balance_table": result,
            "summary": {
                "车队总数": len(result),
                "总运单": sum(r["运单数"] for r in result),
                "平均运单": sum(r["运单数"] for r in result) / max(len(result), 1)
            }
        }
    
    def get_optimization_suggestions(self):
        """生成优化建议"""
        if not self.data:
            return []
        
        suggestions = []
        
        # 分析供需失衡
        balance = self.get_balance_report()
        if "balance_table" in balance:
            table = balance["balance_table"]
            
            if table:
                max_orders = max(r["运单数"] for r in table)
                min_orders = min(r["运单数"] for r in table)
                
                # 运力差异过大
                if max_orders / max(min_orders, 1) > 2:
                    suggestions.append({
                        "type": "紧急",
                        "title": "车队运力差异过大",
                        "content": f"运力差距{max_orders/min_orders:.1f}倍，建议跨区调配",
                        "action": "从高运力车队调配资源至低运力车队"
                    })
            
            # 检查线路过少的车队
            for r in table:
                if r["线路数"] < 5:
                    suggestions.append({
                        "type": "中期",
                        "title": f"{r['车队']} 线路单一",
                        "content": f"仅{r['线路数']}条线路，返程空驶风险高",
                        "action": "开拓新线路，增加对流运输"
                    })
        
        # 分析跨省运输
        cross_province = 0
        within_province = 0
        
        for row in self.data:
            from_prov = row.get('始发省', '')
            to_prov = row.get('目的省', '')
            if from_prov and to_prov:
                if from_prov == to_prov:
                    within_province += 1
                else:
                    cross_province += 1
        
        total = cross_province + within_province
        if total > 0:
            cross_rate = cross_province / total * 100
            if cross_rate > 60:
                suggestions.append({
                    "type": "中期",
                    "title": "跨省运输比例过高",
                    "content": f"跨省运输占比{cross_rate:.1f}%，增加短驳运输可降低成本",
                    "action": "优化区域配送网络，减少长途运输"
                })
        
        # 品牌集中度
        brand_count = Counter()
        for row in self.data:
            brand = row.get('品牌', '')
            if brand:
                brand_count[brand] += 1
        
        if brand_count:
            top_brand = brand_count.most_common(1)[0]
            top_rate = top_brand[1] / len(self.data) * 100
            if top_rate > 30:
                suggestions.append({
                    "type": "长期",
                    "title": f"品牌依赖度过高",
                    "content": f"{top_brand[0]}占比{top_rate:.1f}%，单一品牌风险高",
                    "action": "多品牌接单，分散经营风险"
                })
        
        return suggestions
    
    def generate_summary(self):
        """生成摘要报告"""
        analysis = self.analyze()
        balance = self.get_balance_report()
        suggestions = self.get_optimization_suggestions()
        
        summary = f"""
📊 整车物流数据分析报告
========================

📈 基础统计
- 总运单数: {analysis.get('total_orders', 0)}
- 车队数量: {len(analysis.get('carriers', {}))}
- 品牌数量: {len(analysis.get('brands', {}))}
- 大区数量: {len(analysis.get('regions', {}))}

🚚 车队运力 TOP5
"""
        carriers = analysis.get('carriers', {})
        for i, (name, count) in enumerate(list(carriers.items())[:5], 1):
            summary += f"{i}. {name}: {count}单\n"
        
        summary += f"""
🏭 品牌分布 TOP5
"""
        brands = analysis.get('brands', {})
        for i, (name, count) in enumerate(list(brands.items())[:5], 1):
            summary += f"{i}. {name}: {count}单\n"
        
        if suggestions:
            summary += "\n💡 优化建议\n"
            for s in suggestions:
                emoji = "🔴" if s["type"] == "紧急" else "🟡" if s["type"] == "中期" else "🟢"
                summary += f"\n{emoji} {s['type']} - {s['title']}\n   {s['content']}\n   → {s['action']}\n"
        
        return summary


def main():
    parser = argparse.ArgumentParser(description='整车物流调度分析工具')
    parser.add_argument('--file', '-f', required=True, help='数据文件路径')
    parser.add_argument('--analyze', '-a', action='store_true', help='执行分析')
    parser.add_argument('--balance', '-b', action='store_true', help='生成供需平衡表')
    parser.add_argument('--suggestions', '-s', action='store_true', help='生成优化建议')
    parser.add_argument('--report', '-r', action='store_true', help='生成完整报告')
    parser.add_argument('--json', '-j', action='store_true', help='JSON格式输出')
    
    args = parser.parse_args()
    
    analyzer = LogisticsAnalyzer(args.file)
    
    # 加载数据
    success, msg = analyzer.load_data()
    if not success:
        print(f"❌ {msg}")
        sys.exit(1)
    
    print(f"✅ {msg}")
    
    # 执行相应操作
    if args.analyze:
        result = analyzer.analyze()
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            carriers = result.get('carriers', {})
            print("\n🚚 车队分布:")
            for name, count in list(carriers.items())[:10]:
                print(f"  {name}: {count}")
    
    if args.balance:
        result = analyzer.get_balance_report()
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print("\n📋 供需平衡表:")
            table = result.get('balance_table', [])
            print(f"{'车队':<15} {'运单数':>8} {'线路数':>8} {'品牌数':>8}")
            print("-" * 45)
            for r in table[:15]:
                print(f"{r['车队']:<15} {r['运单数']:>8} {r['线路数']:>8} {r['品牌数']:>8}")
    
    if args.suggestions:
        result = analyzer.get_optimization_suggestions()
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print("\n💡 优化建议:")
            for s in result:
                emoji = "🔴" if s["type"] == "紧急" else "🟡" if s["type"] == "中期" else "🟢"
                print(f"\n{emoji} {s['type']} - {s['title']}")
                print(f"   {s['content']}")
                print(f"   → {s['action']}")
    
    if args.report:
        print(analyzer.generate_summary())


if __name__ == '__main__':
    main()
