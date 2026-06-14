"""管理员工具: 生成激活码、管理用户."""

import sys
from datetime import datetime

from .license import generate_license_key
from .user_db import add_license, list_users, update_license_status, reset_devices


def cmd_generate(args):
    user = args.user
    if not user:
        print("用法: --user <用户名> [--expire YYYYMM] [--permanent]")
        return

    if getattr(args, "permanent", False):
        expire = "999912"
    else:
        expire = getattr(args, "expire", None) or (datetime.now().strftime("%Y%m") + "01")
        # default: expire end of current year
        if not getattr(args, "expire", None):
            expire = datetime.now().strftime("%Y") + "12"

    key = generate_license_key(user, expire)
    import hashlib
    key_hash = hashlib.sha256(key.encode()).hexdigest()

    max_dev = int(getattr(args, "devices", 1) or 1)
    if add_license(user, key_hash, expire, max_dev):
        perm_str = "永久" if expire == "999912" else f"到期 {expire[:4]}-{expire[4:]}"
        print(f"用户: {user}")
        print(f"激活码: {key}")
        print(f"有效期: {perm_str}")
        print(f"设备数: {max_dev}")
        print("已保存到数据库")
    else:
        print("添加失败（可能已存在）")


def cmd_list(args):
    users = list_users()
    if not users:
        print("暂无用户")
        return
    print(f"{'ID':<4} {'用户名':<12} {'到期':<10} {'设备':<6} {'状态':<6} {'创建时间'}")
    print("-" * 60)
    for u in users:
        em = u["expire_month"]
        exp_str = "永久" if em == "999912" else f"{em[:4]}-{em[4:]}"
        dev_str = f"{u['device_count']}/{u['max_devices']}"
        act_str = "启用" if u["active"] else "禁用"
        print(f"{u['id']:<4} {u['user_name']:<12} {exp_str:<10} {dev_str:<6} {act_str:<6} {u['created_at']}")


def cmd_disable(args):
    user = args.user
    if not user:
        print("用法: --user <用户名>")
        return
    update_license_status(user, False)
    print(f"已禁用用户: {user}")


def cmd_enable(args):
    user = args.user
    if not user:
        print("用法: --user <用户名>")
        return
    update_license_status(user, True)
    print(f"已启用用户: {user}")


def cmd_reset(args):
    user = args.user
    if not user:
        print("用法: --user <用户名>")
        return
    users = [u for u in list_users() if u["user_name"] == user]
    if not users:
        print(f"找不到用户: {user}")
        return
    # Reset device binding for all licenses of this user
    print(f"用户 {user}: 手动重置设备绑定（联系管理员操作）")
    print("请联系开发者手动操作数据库")


def cmd_stats(args):
    users = list_users()
    active = [u for u in users if u["active"]]
    print(f"总用户: {len(users)}")
    print(f"活跃: {len(active)}")
    print(f"本月新增: {sum(1 for u in users if u['created_at'] and u['created_at'][:7] == datetime.now().strftime('%Y-%m'))}")


def main():
    if len(sys.argv) < 2:
        print("""管理员工具:
  generate --user 用户名 [--expire YYYYMM] [--permanent] [--devices N]  生成激活码
  list                                                                    查看所有用户
  disable --user 用户名                                                   禁用用户
  enable --user 用户名                                                    启用用户
  stats                                                                   统计
""")
        return

    cmd = sys.argv[1]
    # Simple arg parsing
    class Args:
        pass
    args = Args()
    args.user = None
    args.expire = None
    args.permanent = False
    args.devices = 1

    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == "--user" and i + 1 < len(sys.argv):
            args.user = sys.argv[i + 1]; i += 2
        elif sys.argv[i] == "--expire" and i + 1 < len(sys.argv):
            args.expire = sys.argv[i + 1]; i += 2
        elif sys.argv[i] == "--permanent":
            args.permanent = True; i += 1
        elif sys.argv[i] == "--devices" and i + 1 < len(sys.argv):
            args.devices = int(sys.argv[i + 1]); i += 2
        else:
            i += 1

    if cmd == "generate":
        cmd_generate(args)
    elif cmd == "list":
        cmd_list(args)
    elif cmd == "disable":
        cmd_disable(args)
    elif cmd == "enable":
        cmd_enable(args)
    elif cmd == "reset":
        cmd_reset(args)
    elif cmd == "stats":
        cmd_stats(args)
    else:
        print(f"未知命令: {cmd}")


if __name__ == "__main__":
    main()
