# 服务器与客户端更新流程文档

## 服务器信息
- **服务器地址**：10.196.174.33  
- **数据库地址**：10.196.155.148  
- ⚠️ **重要信息**：生产和测试数据库均在同一服务器上，但使用不同的数据库名。访问时务必谨慎操作。

## 云服务器访问前置条件
- 需向服务器所属人 **zhangbiao** 申请访问权限  
- 经由 **AWP 平台**进入服务器  
- 访问链接：<https://xcloud.lenovo.com/awp/pages/webaccess/os>

## 目录与项目路径
- **nginx 配置存放位置**：`/etc/nginx/conf.d/patvs_flask_site.conf`
- **项目存放位置**：`/home/Admin/code`

---

# 一、服务器前端更新流程

1. 拉取最新代码  
   ```bash
   git fetch master
   ```

2. 进行前端构建  
   ```bash
   npm run build
   ```

3. 重新赋权  
   ```bash
   sudo chmod o+x /home/Admin/code
   sudo chmod o+x /home/Admin/code/test-tracking-system-vue
   sudo chmod -R o+rX /home/Admin/code/test-tracking-system-vue/dist
   ```

---

# 二、服务器后端更新流程

1. 拉取最新代码  
   ```bash
   git fetch master
   ```

2. 查看当前 gunicorn 进程  
   ```bash
   ps aux | grep gunicorn
   ```

3. 杀死进程（⚠️ 会中断服务，需下班后执行）  
   ```bash
   sudo kill -9 <pid>
   ```

4. 重启 gunicorn 服务  
   ```bash
   nohup sudo python3.10 -m gunicorn "app:create_app('development')"      --workers 4 --bind 127.0.0.1:8000      >/dev/null 2>&1 &
   ```

---

# 三、日志查询

```bash
sudo tail -n 100 /var/log/nginx/error.log
sudo tail -n 100 logs/error.log
```

---

# 四、客户端更新流程

## 前置条件： 向 ruansp1@lenovo.com 申请添加签名邮件白名单

## 1. FTP 服务器信息
- **IP**：10.184.7.135  
- **Username**：sign  
- **Password**：a;sldkfjz.

## 2. 上传待签名文件
将打包好的 `.exe` 文件上传至 FTP 的 **In** 文件夹。

## 3. 发送签名请求邮件
- 邮件主题：`LENOVO SIGNING REQUEST`
- 内容：可随意填写
- 发送至：ruansp1@lenovo.com

## 4. 获取签名文件
等待签名完成邮件 → 根据邮件提示访问 FTP **Out** 文件夹 → 下载已签名版本。

## 5. OTA 包处理
将签名后的客户端压缩成 `.zip` 文件，放入：

```
/home/Admin/code/testtrackingsystem/ota_packages
```

## 6. 更新 OTA 配置
编辑：

``` 
/home/Admin/code/testtrackingsystem/ota_release.json
```

填写更新信息即可。

---

