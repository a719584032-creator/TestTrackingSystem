#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
pytest 测试运行脚本
支持多种运行模式和参数配置
"""
import os
import sys
import argparse
import subprocess


def run_tests(args):
    """运行测试"""
    # 基础pytest命令
    cmd = ["python", "-m", "pytest"]

    # 添加详细输出
    cmd.extend(["-v", "-s"])

    # 添加测试覆盖率
    if args.coverage:
        cmd.extend(["--cov=.", "--cov-report=html", "--cov-report=term"])

    # 添加并行执行
    if args.parallel and args.parallel > 1:
        cmd.extend(["-n", str(args.parallel)])

    # 添加标记过滤
    if args.markers:
        for marker in args.markers:
            cmd.extend(["-m", marker])

    # 添加关键词过滤
    if args.keyword:
        cmd.extend(["-k", args.keyword])

    # 添加失败时停止
    if args.stop_on_first_fail:
        cmd.append("-x")

    # 添加重试
    if args.reruns:
        cmd.extend(["--reruns", str(args.reruns)])

    # 添加HTML报告
    if args.html_report:
        cmd.extend(["--html", args.html_report, "--self-contained-html"])

    # 添加JUnit XML报告
    if args.junit_xml:
        cmd.extend(["--junit-xml", args.junit_xml])

    # 添加测试路径
    if args.test_path:
        cmd.append(args.test_path)

    # 设置环境变量
    env = os.environ.copy()
    if args.base_url:
        env["API_BASE_URL"] = args.base_url
    if args.admin_username:
        env["ADMIN_USERNAME"] = args.admin_username
    if args.admin_password:
        env["ADMIN_PASSWORD"] = args.admin_password

    print(f"执行命令: {' '.join(cmd)}")
    print(f"环境变量: API_BASE_URL={env.get('API_BASE_URL', 'default')}")
    print("-" * 60)

    # 执行测试
    result = subprocess.run(cmd, env=env)
    return result.returncode


def main():
    parser = argparse.ArgumentParser(description="API测试运行脚本")

    # 服务配置
    parser.add_argument("--base-url", default="http://127.0.0.1",
                        help="API服务基础URL")
    parser.add_argument("--admin-username", default="admin",
                        help="管理员用户名")
    parser.add_argument("--admin-password", default="Admin123!",
                        help="管理员密码")

    # 测试配置
    parser.add_argument("--test-path", default=".",
                        help="测试路径")
    parser.add_argument("-k", "--keyword",
                        help="按关键词过滤测试")
    parser.add_argument("-m", "--markers", action="append",
                        help="按标记过滤测试 (可多次使用)")
    parser.add_argument("-x", "--stop-on-first-fail", action="store_true",
                        help="遇到第一个失败就停止")
    parser.add_argument("--reruns", type=int, default=0,
                        help="失败重试次数")

    # 并行和性能
    parser.add_argument("-n", "--parallel", type=int, default=1,
                        help="并行执行进程数")

    # 报告选项
    parser.add_argument("--coverage", action="store_true",
                        help="生成覆盖率报告")
    parser.add_argument("--html-report",
                        help="HTML报告文件路径")
    parser.add_argument("--junit-xml",
                        help="JUnit XML报告文件路径")

    args = parser.parse_args()

    # 检查pytest是否安装
    try:
        import pytest
    except ImportError:
        print("错误: 未安装pytest，请运行: pip install pytest")
        return 1

    # 检查可选依赖
    optional_deps = []
    if args.parallel and args.parallel > 1:
        try:
            import pytest_xdist
        except ImportError:
            optional_deps.append("pytest-xdist")

    if args.coverage:
        try:
            import pytest_cov
        except ImportError:
            optional_deps.append("pytest-cov")

    if args.reruns:
        try:
            import pytest_rerunfailures
        except ImportError:
            optional_deps.append("pytest-rerunfailures")


