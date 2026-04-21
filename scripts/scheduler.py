#!/usr/bin/env python3
"""
市场研究定时任务调度器

功能：
- 根据当前时间自动判断执行哪种时间周期的分析
- 支持 1h, 4h, 1d 三种分析周期
- 整点自动触发分析报告生成
"""

import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

SCRIPT_DIR = Path(__file__).parent


def run_analysis(timeframe):
    """执行指定时间周期的分析"""
    print(f"\n{'='*60}")
    print(f"执行 {timeframe} 技术分析")
    print(f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")
    
    script_path = SCRIPT_DIR / 'analyze.py'
    
    try:
        result = subprocess.run(
            [sys.executable, str(script_path), timeframe],
            cwd=str(SCRIPT_DIR),
            capture_output=False,
            text=True
        )
        
        if result.returncode != 0:
            print(f"\n分析执行失败，返回码：{result.returncode}")
            return False
        
        return True
    except Exception as e:
        print(f"\n分析执行异常：{e}")
        return False


def run_sync():
    """执行数据同步"""
    print(f"\n{'='*60}")
    print(f"执行市场数据同步")
    print(f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")
    
    script_path = SCRIPT_DIR / 'sync_data.py'
    
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(SCRIPT_DIR),
            capture_output=False,
            text=True
        )
        
        if result.returncode != 0:
            print(f"\n数据同步失败，返回码：{result.returncode}")
            return False
        
        return True
    except Exception as e:
        print(f"\n数据同步异常：{e}")
        return False


def main():
    """主函数"""
    now = datetime.now()
    hour = now.hour
    minute = now.minute
    
    # 获取命令行参数
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == 'sync':
            # 数据同步
            run_sync()
        elif command in ['15m', '1h', '4h', '1d']:
            # 指定时间周期分析
            run_analysis(command)
        else:
            print(f"未知命令：{command}")
            print("用法：python scheduler.py [sync|15m|1h|4h|1d]")
            sys.exit(1)
    else:
        # 自动模式：根据当前时间判断执行哪种分析
        print(f"自动调度模式 - {now.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 每 15 分钟同步数据
        if minute % 15 == 0:
            print("\n执行数据同步...")
            run_sync()
        
        # 每小时整点执行 1h 分析
        if minute == 0:
            run_analysis('1h')
            
            # 每 4 小时整点执行 4h 分析
            if hour % 4 == 0:
                run_analysis('4h')
            
            # 每天 0 点执行 1d 分析
            if hour == 0:
                run_analysis('1d')
        
        print("\n调度完成")


if __name__ == '__main__':
    main()
