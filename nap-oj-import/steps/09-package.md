# Step 9: 清理

## 目标

清理工作目录，保留最终交付文件。

## 最终交付目录结构

```
{slug}/
├── problem.json
├── problem.md
└── testcases/
    ├── 1.in
    ├── 1.out
    ├── 2.in
    ├── 2.out
    └── ...
```

**只保留以上文件**，删除所有开发工具文件。

## 清理

```bash
cd {WORK_DIR}
rm -f std mkdata *.exe
rm -f std.cpp mkdata.cpp mkin.h boundary.md
rm -f testcases/*.zip
```

## 重命名工作目录

将 `work_` 前缀去掉，只保留 slug：

```bash
cd ..
mv {WORK_DIR} {slug}
# {WORK_DIR} = {slug}
```

## 完成

目录 `{slug}/` 即为最终交付。
