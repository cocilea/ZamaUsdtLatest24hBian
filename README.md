# -

## Binance Zama/Usdt 交易对最近24小时，15分钟级别，点阵图
## 结合FLASK实现WEB展示

---

## Ubuntu 24.04 部署步骤

### 1. 更新系统软件包

```bash
sudo apt update && sudo apt upgrade -y
```

### 2. 安装 Python 3 及依赖工具

Ubuntu 24.04 默认自带 Python 3.12，安装 pip 和 venv：

```bash
sudo apt install -y python3-pip python3-venv git
```

### 3. 克隆项目

```bash
git clone https://github.com/cocilea/ZamaUsdtLatest24hBian.git
cd ZamaUsdtLatest24hBian
```

### 4. 创建并激活虚拟环境

```bash
python3 -m venv venv
source venv/bin/activate
```

### 5. 安装项目依赖

```bash
pip install -r requirements.txt
```

### 6. 运行应用

```bash
python app.py
```

启动后，在浏览器中访问 `http://<服务器IP>:5000` 即可查看图表。

> **注意**：`python app.py` 使用的是 Flask 内置开发服务器，仅适合本地测试。若需对外提供服务，请使用生产级 WSGI 服务器（如 gunicorn，见下方）并在前端配置 Nginx 反向代理及 HTTPS，以避免将开发服务器直接暴露到公网。

> 如需在后台持续运行，可使用 `nohup` 或配置 systemd 服务（见下方）。

---

### （可选）使用 systemd 设置为系统服务

建议安装 [gunicorn](https://gunicorn.org/) 作为生产 WSGI 服务器：

```bash
pip install gunicorn
```

1. 创建服务文件（将 `/home/<your_user>` 替换为实际路径）：

```bash
sudo nano /etc/systemd/system/zama-chart.service
```

2. 填入以下内容：

```ini
[Unit]
Description=ZAMA/USDT Price Chart Flask App
After=network.target

[Service]
User=<your_user>
WorkingDirectory=/home/<your_user>/ZamaUsdtLatest24hBian
ExecStart=/home/<your_user>/ZamaUsdtLatest24hBian/venv/bin/gunicorn -w 2 -b 0.0.0.0:5000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

3. 启用并启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable zama-chart
sudo systemctl start zama-chart
```

4. 查看服务状态：

```bash
sudo systemctl status zama-chart
```
