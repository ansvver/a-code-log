#!/usr/bin/env bash
#
# ShadowsocksR 一键部署管理脚本
# 支持: CentOS 6/7/8, Ubuntu 16+, Debian 8+
# 功能: 安装/卸载/启停/配置/BBR加速/多链接批量部署
#
# 用法:
#   ./ssr_deploy.sh                     # 交互菜单
#   ./ssr_deploy.sh install             # 交互式安装
#   ./ssr_deploy.sh install -f links.txt  # 从文件批量导入 SSR 链接安装
#   ./ssr_deploy.sh start|stop|restart|status|log|uninstall|bbr
#

set -euo pipefail

# ==================== 颜色定义 ====================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# ==================== 全局变量 ====================
SSR_DIR="/usr/local/shadowsocksr"
SSR_CONF="/etc/shadowsocksr/config.json"
SSR_CONF_DIR="/etc/shadowsocksr"
SSR_LOG="/var/log/shadowsocksr.log"
SSR_PID="/var/run/shadowsocksr.pid"
SSR_REPO="https://github.com/shadowsocksrr/shadowsocksr.git"
SERVICE_NAME="shadowsocksr"
SSR_LINK_FILE=""         # -f 参数指定的 SSR 链接文件
MULTI_PORTS=()           # 多链接解析后收集的所有端口

# SSR 配置参数（单链接/手动模式使用，批量模式中循环赋值）
SSR_SERVER=""
SSR_PORT=""
SSR_PASSWORD=""
SSR_METHOD=""
SSR_PROTOCOL=""
SSR_OBFS=""
SSR_PROTO_PARAM=""
SSR_OBFS_PARAM=""

# ==================== 工具函数 ====================

msg_info()  { echo -e "${BLUE}[INFO]${NC} $*"; }
msg_ok()    { echo -e "${GREEN}[OK]${NC} $*"; }
msg_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
msg_error() { echo -e "${RED}[ERROR]${NC} $*"; }

check_root() {
    if [[ $EUID -ne 0 ]]; then
        msg_error "请以 root 用户运行此脚本"
        exit 1
    fi
}

detect_os() {
    if [[ -f /etc/os-release ]]; then
        # 从 os-release 读取发行版 ID
        local os_id
        os_id=$(. /etc/os-release && echo "${ID:-}")
        local os_id_like
        os_id_like=$(. /etc/os-release && echo "${ID_LIKE:-}")
    fi

    if [[ -f /etc/redhat-release ]] || [[ "${os_id:-}" =~ ^(centos|rhel|rocky|alma|opencloudos|tencentos|fedora|openEuler|anolis|alinux)$ ]] || [[ "${os_id_like:-}" =~ rhel|centos|fedora ]]; then
        OS="rhel"
        # 优先用 dnf，没有则回退 yum
        if command -v dnf &>/dev/null; then
            PM="dnf"
        else
            PM="yum"
        fi
    elif [[ "${os_id:-}" == "ubuntu" ]] || [[ "${os_id_like:-}" =~ ubuntu ]]; then
        OS="ubuntu"
        PM="apt-get"
    elif [[ "${os_id:-}" == "debian" ]] || [[ "${os_id_like:-}" =~ debian ]]; then
        OS="debian"
        PM="apt-get"
    else
        msg_error "不支持的操作系统 (ID=${os_id:-unknown}, ID_LIKE=${os_id_like:-unknown})"
        msg_error "请反馈你的 /etc/os-release 内容"
        exit 1
    fi
    msg_info "检测到系统: ${os_id:-$OS}, 包管理器: ${PM}"
}

install_dependencies() {
    msg_info "安装依赖..."
    if [[ "$PM" == "yum" || "$PM" == "dnf" ]]; then
        $PM install -y python3 git wget curl unzip libsodium openssl-devel
    else
        apt-get update
        apt-get install -y python3 git wget curl unzip libsodium-dev openssl
    fi
    msg_ok "依赖安装完成"
}

# 列出当前所有 SSR 服务名（支持多实例发现）
list_ssr_services() {
    local services=()
    # 多端口实例: shadowsocksr-PORT
    for f in /etc/systemd/system/${SERVICE_NAME}-*.service; do
        [[ -f "$f" ]] || continue
        local name
        name=$(basename "$f" .service)
        services+=("$name")
    done
    # 单实例: shadowsocksr
    if [[ -f "/etc/systemd/system/${SERVICE_NAME}.service" ]]; then
        services+=("$SERVICE_NAME")
    fi
    echo "${services[@]}"
}

# ==================== SSR 链接解析 ====================

# base64 解码（兼容 URL-safe base64 和缺少 padding 的情况）
safe_b64_decode() {
    local input="$1"
    # 替换 URL-safe 字符
    input="${input//-/+}"
    input="${input//_//}"
    # 补齐 padding
    local pad=$(( 4 - ${#input} % 4 ))
    if [[ $pad -ne 4 ]]; then
        for ((i=0; i<pad; i++)); do
            input="${input}="
        done
    fi
    echo "$input" | base64 -d 2>/dev/null
}

parse_ssr_link() {
    local link="$1"

    # 去掉 ssr:// 前缀
    local encoded="${link#ssr://}"

    # base64 解码得到主体
    local decoded
    decoded=$(safe_b64_decode "$encoded")

    if [[ -z "$decoded" ]]; then
        msg_error "SSR 链接解码失败"
        return 1
    fi

    # 格式: server:port:protocol:method:obfs:password_b64/?params
    # 分离主体和参数
    local main_part="${decoded%%/*}"
    local param_part="${decoded#*/?}"

    # 使用 : 分割主体部分
    IFS=':' read -r SSR_SERVER SSR_PORT SSR_PROTOCOL SSR_METHOD SSR_OBFS SSR_PASSWORD_B64 <<< "$main_part"

    # 解码密码
    SSR_PASSWORD=$(safe_b64_decode "$SSR_PASSWORD_B64")

    # 解析可选参数
    SSR_OBFS_PARAM=""
    SSR_PROTO_PARAM=""
    if [[ "$param_part" != "$decoded" ]]; then
        # 提取 obfsparam
        if [[ "$param_part" =~ obfsparam=([^&]*) ]]; then
            SSR_OBFS_PARAM=$(safe_b64_decode "${BASH_REMATCH[1]}")
        fi
        # 提取 protoparam
        if [[ "$param_part" =~ protoparam=([^&]*) ]]; then
            SSR_PROTO_PARAM=$(safe_b64_decode "${BASH_REMATCH[1]}")
        fi
    fi

    msg_ok "SSR 链接解析成功"
    echo -e "  服务器:   ${CYAN}${SSR_SERVER}${NC}"
    echo -e "  端口:     ${CYAN}${SSR_PORT}${NC}"
    echo -e "  协议:     ${CYAN}${SSR_PROTOCOL}${NC}"
    echo -e "  加密:     ${CYAN}${SSR_METHOD}${NC}"
    echo -e "  混淆:     ${CYAN}${SSR_OBFS}${NC}"
    echo -e "  密码:     ${CYAN}${SSR_PASSWORD}${NC}"
    [[ -n "$SSR_PROTO_PARAM" ]] && echo -e "  协议参数: ${CYAN}${SSR_PROTO_PARAM}${NC}"
    [[ -n "$SSR_OBFS_PARAM" ]]  && echo -e "  混淆参数: ${CYAN}${SSR_OBFS_PARAM}${NC}"
}

# ==================== 批量解析 SSR 链接文件 ====================

# 从文件读取多行 SSR 链接，逐行解析并为每条生成独立配置
# 文件格式: 每行一个 ssr:// 链接，空行和 # 开头的注释行会被跳过
parse_ssr_file() {
    local file="$1"
    if [[ ! -f "$file" ]]; then
        msg_error "SSR 链接文件不存在: ${file}"
        return 1
    fi

    local count=0
    local line_num=0

    mkdir -p "$SSR_CONF_DIR"
    MULTI_PORTS=()

    echo ""
    echo -e "${BOLD}===== 批量解析 SSR 链接 =====${NC}"

    while IFS= read -r line || [[ -n "$line" ]]; do
        line_num=$((line_num + 1))

        # 去除首尾空白
        line=$(echo "$line" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')

        # 跳过空行和注释
        [[ -z "$line" ]] && continue
        [[ "$line" == \#* ]] && continue

        # 确保是 ssr:// 开头
        if [[ "$line" != ssr://* ]]; then
            msg_warn "第 ${line_num} 行不是有效 SSR 链接，已跳过: ${line:0:40}..."
            continue
        fi

        echo ""
        echo -e "${BLUE}--- 第 ${line_num} 行 ---${NC}"

        if parse_ssr_link "$line"; then
            count=$((count + 1))
            MULTI_PORTS+=("$SSR_PORT")

            # 为每个端口生成独立配置文件
            local conf_file="${SSR_CONF_DIR}/config_${SSR_PORT}.json"
            generate_single_config "$conf_file"
        else
            msg_warn "第 ${line_num} 行解析失败，已跳过"
        fi
    done < "$file"

    echo ""
    if [[ $count -eq 0 ]]; then
        msg_error "文件中没有解析到有效的 SSR 链接"
        return 1
    fi

    msg_ok "共解析 ${count} 条 SSR 链接"
    echo -e "  端口列表: ${CYAN}${MULTI_PORTS[*]}${NC}"
}

# ==================== 手动输入配置 ====================

input_config_manually() {
    echo ""
    read -rp "服务器地址: " SSR_SERVER
    read -rp "服务器端口 [默认 8388]: " SSR_PORT
    SSR_PORT="${SSR_PORT:-8388}"
    read -rp "密码: " SSR_PASSWORD

    echo "加密方式选择:"
    echo "  1) aes-256-cfb    2) aes-128-cfb    3) chacha20"
    echo "  4) chacha20-ietf  5) aes-256-gcm    6) none"
    read -rp "选择 [默认 1]: " method_choice
    case "${method_choice:-1}" in
        1) SSR_METHOD="aes-256-cfb" ;;
        2) SSR_METHOD="aes-128-cfb" ;;
        3) SSR_METHOD="chacha20" ;;
        4) SSR_METHOD="chacha20-ietf" ;;
        5) SSR_METHOD="aes-256-gcm" ;;
        6) SSR_METHOD="none" ;;
        *) SSR_METHOD="aes-256-cfb" ;;
    esac

    echo "协议选择:"
    echo "  1) origin            2) auth_sha1_v4"
    echo "  3) auth_aes128_md5   4) auth_aes128_sha1"
    echo "  5) auth_chain_a      6) auth_chain_b"
    read -rp "选择 [默认 1]: " proto_choice
    case "${proto_choice:-1}" in
        1) SSR_PROTOCOL="origin" ;;
        2) SSR_PROTOCOL="auth_sha1_v4" ;;
        3) SSR_PROTOCOL="auth_aes128_md5" ;;
        4) SSR_PROTOCOL="auth_aes128_sha1" ;;
        5) SSR_PROTOCOL="auth_chain_a" ;;
        6) SSR_PROTOCOL="auth_chain_b" ;;
        *) SSR_PROTOCOL="origin" ;;
    esac

    echo "混淆方式选择:"
    echo "  1) plain           2) http_simple"
    echo "  3) http_post       4) tls1.2_ticket_auth"
    read -rp "选择 [默认 1]: " obfs_choice
    case "${obfs_choice:-1}" in
        1) SSR_OBFS="plain" ;;
        2) SSR_OBFS="http_simple" ;;
        3) SSR_OBFS="http_post" ;;
        4) SSR_OBFS="tls1.2_ticket_auth" ;;
        *) SSR_OBFS="plain" ;;
    esac

    read -rp "协议参数 [可留空]: " SSR_PROTO_PARAM
    read -rp "混淆参数 [可留空]: " SSR_OBFS_PARAM

    SSR_PROTO_PARAM="${SSR_PROTO_PARAM:-}"
    SSR_OBFS_PARAM="${SSR_OBFS_PARAM:-}"
}

# ==================== 生成配置文件 ====================

# 生成单个配置文件（使用当前全局变量中的参数）
generate_single_config() {
    local conf_file="${1:-$SSR_CONF}"
    mkdir -p "$(dirname "$conf_file")"

    cat > "$conf_file" <<CONF
{
    "server": "0.0.0.0",
    "server_ipv6": "::",
    "server_port": ${SSR_PORT},
    "local_address": "127.0.0.1",
    "local_port": 1080,
    "password": "${SSR_PASSWORD}",
    "method": "${SSR_METHOD}",
    "protocol": "${SSR_PROTOCOL}",
    "protocol_param": "${SSR_PROTO_PARAM:-}",
    "obfs": "${SSR_OBFS}",
    "obfs_param": "${SSR_OBFS_PARAM:-}",
    "speed_limit_per_con": 0,
    "speed_limit_per_user": 0,
    "additional_ports": {},
    "additional_ports_only": false,
    "timeout": 120,
    "udp_timeout": 60,
    "dns_ipv6": false,
    "connect_verbose_info": 0,
    "redirect": "",
    "fast_open": false
}
CONF
    msg_ok "配置文件已生成: ${conf_file}"
}

generate_config() {
    generate_single_config "$SSR_CONF"
}

# ==================== 安装 SSR ====================

install_ssr() {
    msg_info "开始安装 ShadowsocksR..."

    install_dependencies

    # 下载 SSR
    if [[ -d "$SSR_DIR" ]]; then
        msg_warn "SSR 目录已存在，将更新..."
        cd "$SSR_DIR" && git pull
    else
        git clone -b manyuser "$SSR_REPO" "$SSR_DIR"
    fi

    # 初始化
    cd "$SSR_DIR"
    if [[ -f setup_cymysql.sh ]]; then
        bash initcfg.sh 2>/dev/null || true
    fi

    # 修补 Python 3.10+ 兼容性问题
    # collections.MutableMapping 在 3.10 移至 collections.abc
    patch_python3_compat

    # 修补 OpenSSL 3.x 兼容性问题
    # OpenSSL 3.0+ 默认禁用 legacy 算法 (RC4, DES, MD5 等)
    patch_openssl3_compat

    msg_ok "ShadowsocksR 安装完成"
}

# 修补 SSR 源码以兼容 Python 3.10+
patch_python3_compat() {
    msg_info "检查 Python 3 兼容性..."

    local py_minor
    py_minor=$(python3 -c 'import sys; print(sys.version_info.minor)' 2>/dev/null || echo "0")

    if [[ "$py_minor" -lt 10 ]]; then
        msg_ok "Python 3.${py_minor}，无需修补"
        return
    fi

    msg_info "Python 3.${py_minor} 检测到，修补 collections.MutableMapping..."

    # 需要修补的文件列表
    local files=(
        "${SSR_DIR}/shadowsocks/lru_cache.py"
        "${SSR_DIR}/shadowsocks/common.py"
        "${SSR_DIR}/shadowsocks/shell.py"
        "${SSR_DIR}/shadowsocks/server.py"
    )

    for f in "${files[@]}"; do
        [[ -f "$f" ]] || continue

        # 修补 collections.MutableMapping -> collections.abc.MutableMapping
        if grep -q 'collections\.MutableMapping' "$f" 2>/dev/null; then
            sed -i 's/collections\.MutableMapping/collections.abc.MutableMapping/g' "$f"
            msg_ok "  已修补: $(basename "$f") (MutableMapping)"
        fi

        # 修补 collections.OrderedDict (某些版本也有问题)
        # 以及其他可能的 collections 子类引用
    done

    msg_ok "Python 3 兼容性修补完成"
}

# 修补 SSR 的 OpenSSL 绑定以兼容 OpenSSL 3.x
# OpenSSL 3.0+ 默认不加载 legacy provider，导致 RC4/DES/BF 等旧算法不可用
# SSR 的 openssl.py 在初始化时会因此 SEGV/异常
patch_openssl3_compat() {
    msg_info "检查 OpenSSL 兼容性..."

    local openssl_major
    openssl_major=$(openssl version 2>/dev/null | head -1 | sed -n 's/.*OpenSSL \([0-9]\).*/\1/p')
    openssl_major="${openssl_major:-1}"

    if [[ "$openssl_major" -lt 3 ]]; then
        msg_ok "OpenSSL $(openssl version 2>/dev/null | head -1 | awk '{print $2}')，无需修补"
        return
    fi

    msg_info "OpenSSL 3.x 检测到，修补 SSR OpenSSL 绑定..."

    local openssl_py="${SSR_DIR}/shadowsocks/crypto/openssl.py"

    if [[ ! -f "$openssl_py" ]]; then
        msg_warn "未找到 openssl.py，跳过"
        return
    fi

    # 检查是否已修补过
    if grep -q 'OSSL_PROVIDER_load' "$openssl_py" 2>/dev/null; then
        msg_ok "openssl.py 已修补过，跳过"
        return
    fi

    # 备份原文件
    cp "$openssl_py" "${openssl_py}.bak"

    # 修补: 在 load_openssl() 函数中加载 legacy 和 default provider
    # 找到 libcrypto 加载的位置，在其后插入 provider 加载代码
    python3 << 'PATCH_SCRIPT'
import re

filepath = "/usr/local/shadowsocksr/shadowsocks/crypto/openssl.py"

with open(filepath, 'r') as f:
    content = f.read()

# 1. 在文件头部的 import 区域后添加 legacy provider 加载逻辑
# 找到 "loaded = False" 或 "load_openssl" 函数

# 策略: 在 load_openssl() 函数体内, libcrypto 加载成功后, 加载 legacy provider
patch_code = '''
def _load_openssl3_legacy():
    """Load OpenSSL 3.x legacy provider for RC4/DES/BF support"""
    try:
        import ctypes
        import ctypes.util
        libcrypto_name = ctypes.util.find_library('crypto')
        if not libcrypto_name:
            return
        libcrypto = ctypes.CDLL(libcrypto_name)
        # OSSL_PROVIDER_load(NULL, "legacy")
        if hasattr(libcrypto, 'OSSL_PROVIDER_load'):
            libcrypto.OSSL_PROVIDER_load.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
            libcrypto.OSSL_PROVIDER_load.restype = ctypes.c_void_p
            libcrypto.OSSL_PROVIDER_load(None, b"legacy")
            libcrypto.OSSL_PROVIDER_load(None, b"default")
    except Exception:
        pass

_load_openssl3_legacy()
'''

# 插入到文件开头的 import 块之后（在第一个函数定义之前）
# 找 "def " 开头的第一行
match = re.search(r'^(def \w+)', content, re.MULTILINE)
if match:
    insert_pos = match.start()
    content = content[:insert_pos] + patch_code + '\n' + content[insert_pos:]

with open(filepath, 'w') as f:
    f.write(content)

print("OK")
PATCH_SCRIPT

    if [[ $? -eq 0 ]]; then
        msg_ok "openssl.py 已修补 (加载 legacy provider)"
    else
        msg_error "openssl.py 修补失败，恢复备份"
        mv "${openssl_py}.bak" "$openssl_py"
        return 1
    fi

    # 同时配置 OpenSSL 的配置文件启用 legacy provider (系统级备选方案)
    local openssl_conf="/etc/ssl/openssl.cnf"
    if [[ -f "$openssl_conf" ]] && ! grep -q 'legacy = legacy_sect' "$openssl_conf" 2>/dev/null; then
        msg_info "配置系统 OpenSSL 启用 legacy provider..."
        cp "$openssl_conf" "${openssl_conf}.bak.ssr"
        cat >> "$openssl_conf" << 'SSLCONF'

# Added by SSR deploy script - enable legacy algorithms
[provider_sect]
default = default_sect
legacy = legacy_sect

[default_sect]
activate = 1

[legacy_sect]
activate = 1
SSLCONF
        msg_ok "系统 OpenSSL legacy provider 已启用"
    fi
}

# ==================== systemd 服务 ====================

# 创建单实例服务
create_service_for_conf() {
    local conf_file="$1"
    local svc_name="$2"
    local pid_file="/var/run/${svc_name}.pid"
    local log_file="/var/log/${svc_name}.log"

    cat > "/etc/systemd/system/${svc_name}.service" <<SERVICE
[Unit]
Description=ShadowsocksR Server (${svc_name})
After=network.target

[Service]
Type=forking
ExecStart=/usr/bin/python3 ${SSR_DIR}/shadowsocks/server.py -c ${conf_file} -d start --pid-file ${pid_file} --log-file ${log_file}
ExecStop=/usr/bin/python3 ${SSR_DIR}/shadowsocks/server.py -c ${conf_file} -d stop --pid-file ${pid_file}
ExecReload=/bin/kill -HUP \$MAINPID
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICE

    systemctl daemon-reload
    systemctl enable "${svc_name}"
    msg_ok "服务 ${svc_name} 已创建并设置开机自启"
}

create_service() {
    if [[ ${#MULTI_PORTS[@]} -gt 0 ]]; then
        # 多端口模式：为每个端口创建独立服务
        for port in "${MULTI_PORTS[@]}"; do
            create_service_for_conf "${SSR_CONF_DIR}/config_${port}.json" "${SERVICE_NAME}-${port}"
        done
    else
        # 单端口模式
        create_service_for_conf "$SSR_CONF" "$SERVICE_NAME"
    fi
}

# ==================== 防火墙配置 ====================

# 为单个端口开放防火墙
open_firewall_port() {
    local port="$1"
    if command -v firewall-cmd &>/dev/null; then
        firewall-cmd --permanent --add-port="${port}/tcp"
        firewall-cmd --permanent --add-port="${port}/udp"
    elif command -v ufw &>/dev/null; then
        ufw allow "${port}/tcp"
        ufw allow "${port}/udp"
    else
        iptables -I INPUT -p tcp --dport "${port}" -j ACCEPT
        iptables -I INPUT -p udp --dport "${port}" -j ACCEPT
    fi
}

configure_firewall() {
    local ports=()

    if [[ ${#MULTI_PORTS[@]} -gt 0 ]]; then
        ports=("${MULTI_PORTS[@]}")
    else
        ports=("${SSR_PORT}")
    fi

    msg_info "配置防火墙规则 (端口: ${ports[*]})..."

    for p in "${ports[@]}"; do
        open_firewall_port "$p"
    done

    # 重载防火墙
    if command -v firewall-cmd &>/dev/null; then
        firewall-cmd --reload
    fi
    if command -v iptables-save &>/dev/null && ! command -v firewall-cmd &>/dev/null && ! command -v ufw &>/dev/null; then
        iptables-save > /etc/iptables.rules 2>/dev/null || true
    fi

    msg_ok "防火墙规则已添加"
}

# ==================== BBR 加速 ====================

enable_bbr() {
    msg_info "检查 BBR 状态..."

    # 检查内核版本 >= 4.9
    local kernel_major kernel_minor
    kernel_major=$(uname -r | cut -d. -f1)
    kernel_minor=$(uname -r | cut -d. -f2)

    if [[ $kernel_major -lt 4 ]] || { [[ $kernel_major -eq 4 ]] && [[ $kernel_minor -lt 9 ]]; }; then
        msg_warn "内核版本 $(uname -r) 不支持 BBR (需要 4.9+)"
        msg_warn "请先升级内核后再启用 BBR"
        return 1
    fi

    # 检查是否已启用
    if sysctl net.ipv4.tcp_congestion_control 2>/dev/null | grep -q bbr; then
        msg_ok "BBR 已启用"
        return 0
    fi

    # 启用 BBR
    cat >> /etc/sysctl.conf <<'EOF'

# BBR congestion control
net.core.default_qdisc=fq
net.ipv4.tcp_congestion_control=bbr
EOF
    sysctl -p

    # 验证
    if sysctl net.ipv4.tcp_congestion_control | grep -q bbr; then
        msg_ok "BBR 加速已启用"
    else
        msg_error "BBR 启用失败"
        return 1
    fi
}

# ==================== 启停管理 ====================

start_ssr() {
    local services
    read -ra services <<< "$(list_ssr_services)"

    if [[ ${#services[@]} -eq 0 ]]; then
        msg_error "未找到已安装的 SSR 服务"
        return 1
    fi

    for svc in "${services[@]}"; do
        if systemctl is-active --quiet "$svc" 2>/dev/null; then
            msg_warn "${svc} 已在运行中"
        else
            systemctl start "$svc"
            sleep 1
            if systemctl is-active --quiet "$svc"; then
                msg_ok "${svc} 启动成功"
            else
                msg_error "${svc} 启动失败，查看日志: journalctl -u ${svc}"
            fi
        fi
    done
}

stop_ssr() {
    local services
    read -ra services <<< "$(list_ssr_services)"

    if [[ ${#services[@]} -eq 0 ]]; then
        msg_error "未找到已安装的 SSR 服务"
        return 1
    fi

    for svc in "${services[@]}"; do
        systemctl stop "$svc" 2>/dev/null || true
        msg_ok "${svc} 已停止"
    done
}

restart_ssr() {
    local services
    read -ra services <<< "$(list_ssr_services)"

    if [[ ${#services[@]} -eq 0 ]]; then
        msg_error "未找到已安装的 SSR 服务"
        return 1
    fi

    for svc in "${services[@]}"; do
        systemctl restart "$svc"
        sleep 1
        if systemctl is-active --quiet "$svc"; then
            msg_ok "${svc} 重启成功"
        else
            msg_error "${svc} 重启失败"
        fi
    done
}

status_ssr() {
    echo ""
    echo -e "${BOLD}===== ShadowsocksR 状态 =====${NC}"

    local services
    read -ra services <<< "$(list_ssr_services)"

    if [[ ${#services[@]} -eq 0 ]]; then
        msg_warn "未找到已安装的 SSR 服务"
        return
    fi

    for svc in "${services[@]}"; do
        echo ""
        echo -e "${BOLD}[${svc}]${NC}"

        # 服务状态
        if systemctl is-active --quiet "$svc" 2>/dev/null; then
            echo -e "  状态: ${GREEN}运行中${NC}"
        else
            echo -e "  状态: ${RED}已停止${NC}"
        fi

        # 从服务文件中提取配置文件路径
        local conf_path
        conf_path=$(grep -oP '(?<=-c )\S+' "/etc/systemd/system/${svc}.service" 2>/dev/null || echo "")

        if [[ -n "$conf_path" ]] && [[ -f "$conf_path" ]]; then
            local port method protocol obfs
            port=$(python3 -c "import json; print(json.load(open('${conf_path}'))['server_port'])" 2>/dev/null || echo "未知")
            method=$(python3 -c "import json; print(json.load(open('${conf_path}'))['method'])" 2>/dev/null || echo "未知")
            protocol=$(python3 -c "import json; print(json.load(open('${conf_path}'))['protocol'])" 2>/dev/null || echo "未知")
            obfs=$(python3 -c "import json; print(json.load(open('${conf_path}'))['obfs'])" 2>/dev/null || echo "未知")
            echo -e "  端口: ${CYAN}${port}${NC}  加密: ${CYAN}${method}${NC}  协议: ${CYAN}${protocol}${NC}  混淆: ${CYAN}${obfs}${NC}"

            # 连接数
            if [[ "$port" != "未知" ]]; then
                local conns
                conns=$(ss -tn sport = :"$port" 2>/dev/null | grep -c ESTAB || echo "0")
                echo -e "  连接: ${CYAN}${conns}${NC}"
            fi
        fi
    done
    echo ""
}

# ==================== 卸载 ====================

uninstall_ssr() {
    echo ""
    read -rp "确定要卸载 ShadowsocksR？(包括所有实例) [y/N]: " confirm
    if [[ "${confirm,,}" != "y" ]]; then
        msg_info "取消卸载"
        return
    fi

    local services
    read -ra services <<< "$(list_ssr_services)"

    # 停止并移除所有服务
    for svc in "${services[@]}"; do
        systemctl stop "$svc" 2>/dev/null || true
        systemctl disable "$svc" 2>/dev/null || true
        rm -f "/etc/systemd/system/${svc}.service"
    done
    systemctl daemon-reload

    rm -rf "$SSR_DIR"
    rm -rf "$SSR_CONF_DIR"

    # 清理日志和 PID 文件
    rm -f /var/log/${SERVICE_NAME}*.log
    rm -f /var/run/${SERVICE_NAME}*.pid

    msg_ok "ShadowsocksR 已完全卸载 (共移除 ${#services[@]} 个服务实例)"
}

# ==================== 查看日志 ====================

view_log() {
    local services
    read -ra services <<< "$(list_ssr_services)"

    if [[ ${#services[@]} -eq 0 ]]; then
        msg_warn "未找到已安装的 SSR 服务"
        return
    fi

    for svc in "${services[@]}"; do
        echo -e "\n${BOLD}===== ${svc} 日志 =====${NC}"
        local log_file="/var/log/${svc}.log"
        if [[ -f "$log_file" ]]; then
            tail -30 "$log_file"
        else
            journalctl -u "$svc" --no-pager -n 30
        fi
    done
}

# ==================== 完整安装流程 ====================

full_install() {
    echo ""
    echo -e "${BOLD}========================================${NC}"
    echo -e "${BOLD}   ShadowsocksR 一键部署${NC}"
    echo -e "${BOLD}========================================${NC}"
    echo ""

    detect_os

    # 如果通过 -f 指定了链接文件，直接走批量流程
    if [[ -n "$SSR_LINK_FILE" ]]; then
        parse_ssr_file "$SSR_LINK_FILE"

        echo ""
        read -rp "以上配置是否正确？[Y/n]: " confirm
        if [[ "${confirm,,}" == "n" ]]; then
            msg_info "已取消安装"
            exit 0
        fi

        install_ssr
        create_service
        configure_firewall
        start_ssr

        echo ""
        read -rp "是否启用 BBR 加速？[Y/n]: " enable_bbr_choice
        if [[ "${enable_bbr_choice,,}" != "n" ]]; then
            enable_bbr
        fi

        status_ssr
        echo -e "${GREEN}${BOLD}批量部署完成！共部署 ${#MULTI_PORTS[@]} 个端口${NC}"
        show_usage_help
        return
    fi

    # 交互式选择配置方式
    echo ""
    echo "请选择配置方式:"
    echo "  1) 粘贴 SSR 链接 (ssr://...)"
    echo "  2) 从文件批量导入 SSR 链接 (每行一个)"
    echo "  3) 手动输入参数"
    echo "  4) 导入已有 config.json"
    read -rp "选择 [1]: " config_mode

    case "${config_mode:-1}" in
        1)
            read -rp "请粘贴 SSR 链接: " ssr_link
            parse_ssr_link "$ssr_link"
            ;;
        2)
            read -rp "SSR 链接文件路径: " link_file_path
            parse_ssr_file "$link_file_path"

            echo ""
            read -rp "以上配置是否正确？[Y/n]: " confirm
            if [[ "${confirm,,}" == "n" ]]; then
                msg_info "已取消安装"
                exit 0
            fi

            install_ssr
            create_service
            configure_firewall
            start_ssr

            echo ""
            read -rp "是否启用 BBR 加速？[Y/n]: " enable_bbr_choice
            if [[ "${enable_bbr_choice,,}" != "n" ]]; then
                enable_bbr
            fi

            status_ssr
            echo -e "${GREEN}${BOLD}批量部署完成！共部署 ${#MULTI_PORTS[@]} 个端口${NC}"
            show_usage_help
            return
            ;;
        3)
            input_config_manually
            ;;
        4)
            read -rp "config.json 路径: " config_path
            if [[ -f "$config_path" ]]; then
                mkdir -p "$(dirname "$SSR_CONF")"
                cp "$config_path" "$SSR_CONF"
                msg_ok "配置文件已导入"
                SSR_PORT=$(python3 -c "import json; print(json.load(open('${SSR_CONF}'))['server_port'])" 2>/dev/null || echo "8388")
                install_ssr
                create_service
                configure_firewall
                start_ssr
                echo ""
                read -rp "是否启用 BBR 加速？[Y/n]: " enable_bbr_choice
                if [[ "${enable_bbr_choice,,}" != "n" ]]; then
                    enable_bbr
                fi
                status_ssr
                show_usage_help
                return
            else
                msg_error "文件不存在: ${config_path}"
                exit 1
            fi
            ;;
    esac

    echo ""
    read -rp "以上配置是否正确？[Y/n]: " confirm
    if [[ "${confirm,,}" == "n" ]]; then
        msg_info "已取消安装"
        exit 0
    fi

    # 执行安装（单链接/手动输入模式）
    install_ssr
    generate_config
    create_service
    configure_firewall
    start_ssr

    # BBR
    echo ""
    read -rp "是否启用 BBR 加速？[Y/n]: " enable_bbr_choice
    if [[ "${enable_bbr_choice,,}" != "n" ]]; then
        enable_bbr
    fi

    # 显示状态
    status_ssr

    echo -e "${GREEN}${BOLD}部署完成！${NC}"
    show_usage_help
}

show_usage_help() {
    echo ""
    echo "管理命令:"
    echo "  $0 start     - 启动所有实例"
    echo "  $0 stop      - 停止所有实例"
    echo "  $0 restart   - 重启所有实例"
    echo "  $0 status    - 查看所有实例状态"
    echo "  $0 log       - 查看日志"
    echo "  $0 uninstall - 卸载"
    echo "  $0 bbr       - 启用 BBR 加速"
    echo ""
    echo "批量部署:"
    echo "  $0 install -f ssr_links.txt"
    echo ""
}

# ==================== 主菜单 ====================

show_menu() {
    echo ""
    echo -e "${BOLD}========================================${NC}"
    echo -e "${BOLD}   ShadowsocksR 管理面板${NC}"
    echo -e "${BOLD}========================================${NC}"
    echo ""
    echo "  1) 完整安装部署"
    echo "  2) 启动 SSR"
    echo "  3) 停止 SSR"
    echo "  4) 重启 SSR"
    echo "  5) 查看状态"
    echo "  6) 查看日志"
    echo "  7) 修改配置"
    echo "  8) 启用 BBR 加速"
    echo "  9) 卸载 SSR"
    echo "  0) 退出"
    echo ""
    read -rp "请选择 [0-9]: " choice

    case "$choice" in
        1) full_install ;;
        2) start_ssr ;;
        3) stop_ssr ;;
        4) restart_ssr ;;
        5) status_ssr ;;
        6) view_log ;;
        7)
            if [[ -f "$SSR_CONF" ]]; then
                ${EDITOR:-vi} "$SSR_CONF"
                read -rp "是否重启 SSR 使配置生效？[Y/n]: " restart_confirm
                if [[ "${restart_confirm,,}" != "n" ]]; then
                    restart_ssr
                fi
            else
                msg_error "配置文件不存在，请先安装"
            fi
            ;;
        8) enable_bbr ;;
        9) uninstall_ssr ;;
        0) exit 0 ;;
        *) msg_error "无效选择" ;;
    esac
}

# ==================== 入口 ====================

main() {
    check_root

    # 解析命令行参数
    local action="${1:-}"
    shift || true

    # 解析 -f 参数
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -f|--file)
                if [[ -z "${2:-}" ]]; then
                    msg_error "-f 参数需要指定 SSR 链接文件路径"
                    exit 1
                fi
                SSR_LINK_FILE="$2"
                shift 2
                ;;
            *)
                msg_error "未知参数: $1"
                exit 1
                ;;
        esac
    done

    case "$action" in
        install)    full_install ;;
        start)      start_ssr ;;
        stop)       stop_ssr ;;
        restart)    restart_ssr ;;
        status)     status_ssr ;;
        log)        view_log ;;
        uninstall)  uninstall_ssr ;;
        bbr)        enable_bbr ;;
        "")
            # 无参数时显示交互菜单
            while true; do
                show_menu
            done
            ;;
        *)
            echo "用法: $0 {install [-f links.txt]|start|stop|restart|status|log|uninstall|bbr}"
            exit 1
            ;;
    esac
}

main "$@"
