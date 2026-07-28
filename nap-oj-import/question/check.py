#!/usr/bin/env python3
"""
对拍验证脚本：独立验证 std.cpp 生成的测试数据是否正确。

用法：
    python check.py [--validator validator.cpp] [--constraints constraints.json]

工作流：
    1. 编译 std.cpp 和 validator.cpp（如果提供）
    2. 对每组 testcases/*.in，分别用 std 和 validator 运行，比对输出
    3. 如果提供了 constraints.json，额外检查每组 .out 是否满足输出约束
    4. 报告所有失败项
"""

import subprocess, os, sys, json, argparse, difflib

TESTCASES_DIR = "testcases"

def compile_cpp(src, out_exe):
    """编译 C++ 文件"""
    result = subprocess.run(
        ["g++", "-std=c++17", "-O2", "-o", out_exe, src],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"[FAIL] 编译 {src} 失败：")
        print(result.stderr)
        return False
    print(f"[ OK ] 编译 {src} 成功")
    return True

def run_exe(exe_path, input_data):
    """运行可执行文件，返回 stdout"""
    try:
        result = subprocess.run(
            [f"./{exe_path}"],
            input=input_data,
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return None, "TIMEOUT"
    except Exception as e:
        return None, str(e)

def get_test_cases():
    """获取所有测试用例号"""
    if not os.path.exists(TESTCASES_DIR):
        return []
    cases = set()
    for f in os.listdir(TESTCASES_DIR):
        if f.endswith(".in"):
            try:
                cases.add(int(f.replace(".in", "")))
            except ValueError:
                pass
    return sorted(cases)

def compare_outputs(std_out, val_out, case_num):
    """比较两个输出是否一致（忽略末尾空白差异）"""
    std_lines = std_out.strip().splitlines()
    val_lines = val_out.strip().splitlines()
    
    # 逐行比较
    if std_lines == val_lines:
        return True, ""
    
    # 宽松比较：strip 每行
    std_stripped = [l.strip() for l in std_lines]
    val_stripped = [l.strip() for l in val_lines]
    if std_stripped == val_stripped:
        return True, ""
    
    # 数值比较（空格/换行不敏感）
    try:
        std_nums = [float(x) for x in " ".join(std_lines).split()]
        val_nums = [float(x) for x in " ".join(val_lines).split()]
        if len(std_nums) == len(val_nums):
            if all(abs(a - b) < 1e-9 for a, b in zip(std_nums, val_nums)):
                return True, ""
    except ValueError:
        pass
    
    diff = "\n".join(difflib.unified_diff(
        std_lines, val_lines,
        fromfile=f"std.out.{case_num}", tofile=f"validator.out.{case_num}"
    ))
    return False, diff

def check_output_constraints(case_num, output, constraints):
    """检查输出是否满足约束"""
    if not constraints:
        return True, ""
    
    issues = []
    output_nums = []
    try:
        output_nums = [float(x) for x in output.split()]
    except ValueError:
        pass
    
    # 检查输出上界
    if "max_answer" in constraints:
        max_ans = constraints["max_answer"]
        for i, val in enumerate(output_nums):
            if val > max_ans:
                issues.append(f"输出值 {val} 超过声明的上界 {max_ans}（题面约束）")
                break
    
    # 检查输出行数
    if "output_lines" in constraints:
        expected_lines = constraints["output_lines"]
        actual_lines = len([l for l in output.strip().splitlines() if l.strip()])
        if actual_lines != expected_lines:
            issues.append(f"输出行数 {actual_lines} ≠ 期望 {expected_lines}")
    
    # 检查单个值范围
    if "output_value_range" in constraints:
        lo, hi = constraints["output_value_range"]
        for val in output_nums:
            if val < lo or val > hi:
                issues.append(f"输出值 {val} 不在范围 [{lo}, {hi}] 内")
                break
    
    return len(issues) == 0, "; ".join(issues)

def main():
    parser = argparse.ArgumentParser(description="对拍验证工具")
    parser.add_argument("--validator", help="独立验证程序源码（如 validator.cpp）")
    parser.add_argument("--constraints", help="输出约束 JSON 文件路径")
    parser.add_argument("--std-src", default="std.cpp", help="标程源码")
    args = parser.parse_args()
    
    # 加载输出约束
    constraints = None
    if args.constraints:
        with open(args.constraints) as f:
            constraints = json.load(f)
        print(f"[INFO] 已加载输出约束：{constraints}")
    
    # 编译 std
    if not compile_cpp(args.std_src, "std_chk"):
        sys.exit(1)
    
    # 编译 validator
    has_validator = False
    if args.validator and os.path.exists(args.validator):
        has_validator = compile_cpp(args.validator, "validator_chk")
    else:
        print("[INFO] 未提供 validator，仅做约束检查")
    
    # 获取测试数据
    cases = get_test_cases()
    if not cases:
        print("[FAIL] testcases/ 目录中无 .in 文件")
        sys.exit(1)
    print(f"[INFO] 共找到 {len(cases)} 组测试数据\n")
    
    # 逐组验证
    mismatch_cases = []
    constraint_issues = []
    
    for case_num in cases:
        in_path = os.path.join(TESTCASES_DIR, f"{case_num}.in")
        out_path = os.path.join(TESTCASES_DIR, f"{case_num}.out")
        
        with open(in_path, "r") as f:
            input_data = f.read()
        with open(out_path, "r") as f:
            expected_out = f.read().strip()
        
        # 运行 std
        std_out, std_err = run_exe("std_chk", input_data)
        if std_out is None:
            print(f"[FAIL] case {case_num}: std 运行失败 - {std_err}")
            mismatch_cases.append(case_num)
            continue
        
        # 检查 std 输出与 .out 一致（最基本检查）
        ok, _ = compare_outputs(std_out, expected_out, case_num)
        if not ok:
            # 可能是格式差异，用数值比较宽松检查
            try:
                s1 = [float(x) for x in std_out.split()]
                s2 = [float(x) for x in expected_out.split()]
                if len(s1) != len(s2) or any(abs(a-b) > 1e-9 for a, b in zip(s1, s2)):
                    print(f"[WARN] case {case_num}: std 输出与 .out 不一致（数值差异）")
                    mismatch_cases.append(case_num)
                    continue
            except:
                print(f"[WARN] case {case_num}: std 输出与 .out 不一致")
                mismatch_cases.append(case_num)
                continue
        
        # 验证器对比
        if has_validator:
            val_out, val_err = run_exe("validator_chk", input_data)
            if val_out is None:
                print(f"[WARN] case {case_num}: validator 运行失败 - {val_err}")
                mismatch_cases.append(case_num)
                continue
            
            ok, diff = compare_outputs(std_out, val_out, case_num)
            if not ok:
                print(f"[FAIL] case {case_num}: std ≠ validator")
                print(f"  std: {std_out[:80]}...")
                print(f"  val: {val_out[:80]}...")
                mismatch_cases.append(case_num)
                continue
        
        # 输出约束检查
        if constraints:
            ok, issue = check_output_constraints(case_num, std_out, constraints)
            if not ok:
                print(f"[FAIL] case {case_num}: 输出约束违反 - {issue}")
                constraint_issues.append((case_num, issue))
                continue
        
        print(f"[ OK ] case {case_num:3d} 通过")
    
    # 汇总
    print(f"\n{'='*50}")
    total = len(cases)
    failed = len(set(mismatch_cases + [c for c, _ in constraint_issues]))
    
    if failed == 0:
        print(f"[PASS] 全部 {total} 组测试数据验证通过！")
    else:
        print(f"[FAIL] {failed}/{total} 组未通过验证")
        if mismatch_cases:
            print(f"  对拍失败: case {mismatch_cases}")
        if constraint_issues:
            for c, issue in constraint_issues:
                print(f"  约束违反: case {c} - {issue}")
    
    # 清理
    for exe in ["std_chk", "validator_chk", "std_chk.exe", "validator_chk.exe"]:
        if os.path.exists(exe):
            os.remove(exe)
    
    sys.exit(0 if failed == 0 else 1)

if __name__ == "__main__":
    main()
