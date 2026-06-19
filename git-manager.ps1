#!/usr/bin/env pwsh
#Requires -Version 7.0

# 修复中文编码
$OutputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$PSDefaultParameterValues['*:Encoding'] = 'utf8'

Set-Location $PSScriptRoot

function Show-Menu {
    Clear-Host
    Write-Host ("=" * 44) -ForegroundColor Cyan
    Write-Host "      Auto Shutdown - Git 管理工具" -ForegroundColor Yellow
    Write-Host ("=" * 44) -ForegroundColor Cyan
    Write-Host "  仓库目录: $(Get-Location)" -ForegroundColor DarkGray
    $branch = git branch --show-current 2>$null
    if ($branch) { Write-Host "  当前分支: $branch" -ForegroundColor DarkGray }
    $remoteUrl = git remote get-url origin 2>$null
    if ($remoteUrl) { Write-Host "  远程仓库: $remoteUrl" -ForegroundColor DarkGray }
    Write-Host ""
    Write-Host "  [1] 推送到 GitHub" -ForegroundColor White
    Write-Host "  [2] 拉取更新 (pull)" -ForegroundColor White
    Write-Host "  [3] 查看状态与差异" -ForegroundColor White
    Write-Host "  [4] 分支管理" -ForegroundColor White
    Write-Host "  [5] 回退到指定版本" -ForegroundColor White
    Write-Host "  [6] 删除历史提交版本" -ForegroundColor White
    Write-Host "  [7] 构建与打包" -ForegroundColor White
    Write-Host "  [8] 推送 Release (自动版本号 & GitHub Release)" -ForegroundColor White
    Write-Host "  [0] 退出" -ForegroundColor White
    Write-Host ""
}

function ReadKey {
    Write-Host "按任意键返回主菜单..." -ForegroundColor DarkGray -NoNewline
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}

function Push-ToGitHub {
    Clear-Host
    Write-Host ("=" * 44) -ForegroundColor Cyan
    Write-Host "  推送到 GitHub" -ForegroundColor Green
    Write-Host ("=" * 44) -ForegroundColor Cyan

    $remote = git remote
    if (-not $remote) {
        Write-Host "`n[!] 未检测到远程仓库 (GitHub)" -ForegroundColor Red
        Write-Host "  请先手动添加远程仓库，例如:" -ForegroundColor Yellow
        Write-Host "    git remote add origin https://github.com/用户名/仓库名.git" -ForegroundColor Gray
        ReadKey; return
    }

    Write-Host "`n远程仓库:" -ForegroundColor Cyan
    git remote -v | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }

    $status = git status --porcelain
    if ($status) {
        Write-Host "`n检测到未提交的更改:" -ForegroundColor Yellow
        git status --short
        $choice = Read-Host "`n是否先提交所有更改? (y/n)"
        if ($choice -in 'y','Y') {
            $msg = Read-Host "请输入提交信息"
            if ([string]::IsNullOrWhiteSpace($msg)) { $msg = "更新 $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" }
            git add -A
            git commit -m "$msg"
        } else {
            Write-Host "已跳过提交." -ForegroundColor DarkGray
        }
    }

    $branch = git branch --show-current
    $confirm = Read-Host "`n确认推送当前分支 ($branch) 到远程? (y/n)"
    if ($confirm -in 'y','Y') {
        Write-Host "正在推送 origin/$branch ..." -ForegroundColor Yellow
        git push origin "$branch"
        if ($LASTEXITCODE -eq 0) {
            Write-Host "`n[OK] 推送成功!" -ForegroundColor Green
        } else {
            Write-Host "`n[!] 推送失败, 请检查网络和权限." -ForegroundColor Red
        }
    }
    ReadKey
}

function Update-FromGitHub {
    Clear-Host
    Write-Host ("=" * 44) -ForegroundColor Cyan
    Write-Host "  拉取更新 (Pull)" -ForegroundColor Green
    Write-Host ("=" * 44) -ForegroundColor Cyan

    $remote = git remote
    if (-not $remote) {
        Write-Host "`n[!] 未检测到远程仓库" -ForegroundColor Red
        ReadKey; return
    }

    $branch = git branch --show-current
    Write-Host "`n当前分支: $branch" -ForegroundColor Cyan
    Write-Host "正在拉取远程更新..." -ForegroundColor Yellow

    git pull origin "$branch"
    if ($LASTEXITCODE -eq 0) {
        Write-Host "`n[OK] 拉取完成!" -ForegroundColor Green
    } else {
        Write-Host "`n[!] 拉取失败, 请检查冲突或网络连接." -ForegroundColor Red
    }
    ReadKey
}

function Show-Status {
    Clear-Host
    Write-Host ("=" * 44) -ForegroundColor Cyan
    Write-Host "  状态与差异" -ForegroundColor Green
    Write-Host ("=" * 44) -ForegroundColor Cyan

    Write-Host "`n[1] 查看工作区状态" -ForegroundColor White
    Write-Host "[2] 查看未暂存的差异 (diff)" -ForegroundColor White
    Write-Host "[3] 查看已暂存的差异 (diff --cached)" -ForegroundColor White
    Write-Host "[4] 查看提交历史 (最近 10 条)" -ForegroundColor White
    Write-Host "[0] 返回主菜单" -ForegroundColor White

    $choice = Read-Host "`n请选择"
    switch ($choice) {
        '1' {
            Write-Host "`n--- git status ---" -ForegroundColor Cyan
            git status
        }
        '2' {
            Write-Host "`n--- git diff ---" -ForegroundColor Cyan
            $diff = git diff
            if ($diff) { Write-Host $diff } else { Write-Host "(无未暂存的更改)" -ForegroundColor DarkGray }
        }
        '3' {
            Write-Host "`n--- git diff --cached ---" -ForegroundColor Cyan
            $diff = git diff --cached
            if ($diff) { Write-Host $diff } else { Write-Host "(无已暂存的更改)" -ForegroundColor DarkGray }
        }
        '4' {
            Write-Host "`n--- git log (最近 10 条) ---" -ForegroundColor Cyan
            git log --oneline --abbrev=8 -10
        }
        '0' { return }
        default { Write-Host "[!] 无效选项" -ForegroundColor Red }
    }
    ReadKey
}

function Show-BranchMenu {
    Clear-Host
    Write-Host ("=" * 44) -ForegroundColor Cyan
    Write-Host "  分支管理" -ForegroundColor Yellow
    Write-Host ("=" * 44) -ForegroundColor Cyan

    do {
        $currentBranch = git branch --show-current
        Write-Host "`n当前分支: " -ForegroundColor Cyan -NoNewline
        Write-Host "$currentBranch" -ForegroundColor Green
        Write-Host ""
        Write-Host "  [1] 查看所有分支" -ForegroundColor White
        Write-Host "  [2] 创建新分支" -ForegroundColor White
        Write-Host "  [3] 切换分支" -ForegroundColor White
        Write-Host "  [4] 合并分支到当前分支" -ForegroundColor White
        Write-Host "  [5] 删除分支" -ForegroundColor White
        Write-Host "  [0] 返回主菜单" -ForegroundColor White

        $choice = Read-Host "`n请选择"
        switch ($choice) {
            '1' { Show-BranchList }
            '2' { New-Branch }
            '3' { Switch-Branch }
            '4' { Merge-Branch }
            '5' { Remove-Branch }
            '0' { break }
            default { Write-Host "[!] 无效选项" -ForegroundColor Red; Start-Sleep -Seconds 1 }
        }
    } while ($choice -ne '0')
}

function Show-BranchList {
    Clear-Host
    Write-Host "--- 本地分支 ---" -ForegroundColor Cyan
    git branch
    Write-Host "`n--- 远程分支 ---" -ForegroundColor Cyan
    $remoteBranches = git branch -r 2>$null
    if ($remoteBranches) {
        Write-Host $remoteBranches
    } else {
        Write-Host "(无远程分支)" -ForegroundColor DarkGray
    }
    Write-Host ""
    ReadKey
}

function New-Branch {
    Clear-Host
    Write-Host "--- 创建新分支 ---" -ForegroundColor Cyan

    $branchName = Read-Host "`n请输入新分支名称"
    if ([string]::IsNullOrWhiteSpace($branchName)) {
        Write-Host "[!] 分支名不能为空" -ForegroundColor Red
        ReadKey; return
    }

    $existing = git branch --list "$branchName"
    if ($existing) {
        Write-Host "[!] 分支 '$branchName' 已存在" -ForegroundColor Red
        ReadKey; return
    }

    $switchNow = Read-Host "创建后立即切换到新分支? (y/n)"
    if ($switchNow -in 'y','Y') {
        git checkout -b "$branchName"
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[OK] 分支 '$branchName' 已创建并切换" -ForegroundColor Green
        } else {
            Write-Host "[!] 创建失败" -ForegroundColor Red
        }
    } else {
        git branch "$branchName"
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[OK] 分支 '$branchName' 已创建" -ForegroundColor Green
        } else {
            Write-Host "[!] 创建失败" -ForegroundColor Red
        }
    }
    ReadKey
}

function Switch-Branch {
    Clear-Host
    Write-Host "--- 切换分支 ---" -ForegroundColor Cyan
    Write-Host "`n本地分支列表:" -ForegroundColor Cyan
    git branch

    $target = Read-Host "`n请输入要切换到的分支名"
    if ([string]::IsNullOrWhiteSpace($target)) {
        Write-Host "[!] 分支名不能为空" -ForegroundColor Red
        ReadKey; return
    }

    $status = git status --porcelain
    if ($status) {
        Write-Host "[!] 工作区有未提交的更改:" -ForegroundColor Yellow
        git status --short
        $stash = Read-Host "是否先暂存 (stash) 当前更改? (y/n/q取消)"
        if ($stash -in 'y','Y') {
            git stash push -m "自动暂存: 切换分支前"
            Write-Host "[OK] 已暂存当前更改" -ForegroundColor Green
        } elseif ($stash -eq 'q') {
            return
        }
    }

    git checkout "$target" 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] 已切换到分支 '$target'" -ForegroundColor Green

        $stashList = git stash list 2>$null
        if ($stashList) {
            $popStash = Read-Host "检测到有暂存记录, 是否恢复最近的暂存? (y/n)"
            if ($popStash -in 'y','Y') {
                git stash pop
                Write-Host "[OK] 已恢复暂存" -ForegroundColor Green
            }
        }
    } else {
        Write-Host "[!] 切换失败, 请检查分支名是否正确" -ForegroundColor Red
    }
    ReadKey
}

function Merge-Branch {
    Clear-Host
    Write-Host "--- 合并分支 ---" -ForegroundColor Cyan

    $current = git branch --show-current
    Write-Host "当前分支: " -ForegroundColor Cyan -NoNewline
    Write-Host "$current" -ForegroundColor Green

    Write-Host "`n可用分支:" -ForegroundColor Cyan
    git branch

    $target = Read-Host "`n请输入要合并到当前分支的目标分支名 (将合并该分支到 $current)"
    if ([string]::IsNullOrWhiteSpace($target)) {
        Write-Host "[!] 分支名不能为空" -ForegroundColor Red
        ReadKey; return
    }
    if ($target -eq $current) {
        Write-Host "[!] 不能合并自己" -ForegroundColor Yellow
        ReadKey; return
    }

    Write-Host "`n合并预览 (将从 $target 合并到 $current):" -ForegroundColor Cyan
    $mergeDiff = git log --oneline --abbrev=8 "$current..$target" 2>$null
    if ($mergeDiff) {
        Write-Host "以下提交将被合并:" -ForegroundColor Yellow
        Write-Host $mergeDiff
    } else {
        Write-Host "(无新提交需要合并)" -ForegroundColor DarkGray
    }

    $confirm = Read-Host "`n确认合并? (y/n)"
    if ($confirm -notin 'y','Y') { Write-Host "已取消." -ForegroundColor DarkGray; ReadKey; return }

    git merge "$target"
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] 合并成功!" -ForegroundColor Green
    } else {
        Write-Host "[!] 合并冲突, 请手动解决冲突后提交" -ForegroundColor Red
    }
    ReadKey
}

function Remove-Branch {
    Clear-Host
    Write-Host "--- 删除分支 ---" -ForegroundColor Red

    $current = git branch --show-current
    Write-Host "当前分支: " -ForegroundColor Cyan -NoNewline
    Write-Host "$current" -ForegroundColor Green

    Write-Host "`n本地分支列表:" -ForegroundColor Cyan
    git branch

    $target = Read-Host "`n请输入要删除的分支名"
    if ([string]::IsNullOrWhiteSpace($target)) {
        Write-Host "[!] 分支名不能为空" -ForegroundColor Red
        ReadKey; return
    }
    if ($target -eq $current) {
        Write-Host "[!] 不能删除当前所在分支, 请先切换到其他分支" -ForegroundColor Red
        ReadKey; return
    }
    if ($target -eq 'main' -or $target -eq 'master') {
        Write-Host "[!] 禁止删除主分支" -ForegroundColor Red
        ReadKey; return
    }

    $confirm = Read-Host "确认删除分支 '$target'? (y/n)"
    if ($confirm -notin 'y','Y') { Write-Host "已取消." -ForegroundColor DarkGray; ReadKey; return }

    git branch -d "$target"
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] 分支 '$target' 已删除" -ForegroundColor Green

        $remoteExists = git branch -r --list "origin/$target" 2>$null
        if ($remoteExists) {
            $delRemote = Read-Host "检测到远程也存在此分支, 是否同步删除? (y/n)"
            if ($delRemote -in 'y','Y') {
                git push origin --delete "$target"
                if ($LASTEXITCODE -eq 0) {
                    Write-Host "[OK] 远程分支 'origin/$target' 已删除" -ForegroundColor Green
                } else {
                    Write-Host "[!] 远程分支删除失败" -ForegroundColor Red
                }
            }
        }
    } else {
        Write-Host "[!] 删除失败, 尝试强制删除? (y/n)" -ForegroundColor Yellow
        $force = Read-Host
        if ($force -in 'y','Y') {
            git branch -D "$target"
            if ($LASTEXITCODE -eq 0) {
                Write-Host "[OK] 分支 '$target' 已强制删除" -ForegroundColor Green
            } else {
                Write-Host "[!] 强制删除失败" -ForegroundColor Red
            }
        }
    }
    ReadKey
}

function Reset-Version {
    Clear-Host
    Write-Host ("=" * 44) -ForegroundColor Cyan
    Write-Host "  回退到指定版本" -ForegroundColor Red
    Write-Host ("=" * 44) -ForegroundColor Cyan

    Write-Host "`n最近提交历史 (最近 15 条):" -ForegroundColor Cyan
    git log --oneline --abbrev=8 -15

    $target = Read-Host "`n输入目标版本号 (提交哈希), 或输入 q 取消"
    if ($target -eq 'q') { ReadKey; return }
    if ([string]::IsNullOrWhiteSpace($target)) { Write-Host "[!] 输入无效" -ForegroundColor Red; ReadKey; return }

    $valid = git cat-file -t $target 2>$null
    if (-not $valid) { Write-Host "[!] 无效的版本号" -ForegroundColor Red; ReadKey; return }

    Write-Host "`n目标版本:" -ForegroundColor Cyan
    git log --oneline -1 $target

    Write-Host "`n!!! 危险操作 !!!" -ForegroundColor Red -BackgroundColor Black
    Write-Host "  [soft] 保留更改在工作区 (推荐)" -ForegroundColor Gray
    Write-Host "  [hard] 丢弃所有更改" -ForegroundColor Red

    do {
        $mode = Read-Host "`n选择回退方式 (soft/hard/q取消)"
        if ($mode -eq 'q') { ReadKey; return }
        $validMode = $mode -in 'soft','hard'
        if (-not $validMode) { Write-Host "请输入 soft 或 hard" -ForegroundColor Yellow }
    } until ($validMode)

    if ($mode -eq 'hard') {
        Write-Host "`n[!] 你将丢失所有未提交的更改!" -ForegroundColor Red -BackgroundColor Black
        $confirm = Read-Host '再次确认, 输入 "yes" 确认执行 hard 回退'
        if ($confirm -ne 'yes') { Write-Host "已取消." -ForegroundColor DarkGray; ReadKey; return }
    } else {
        $confirm = Read-Host "确认 soft 回退到 $target ? (y/n)"
        if ($confirm -notin 'y','Y') { Write-Host "已取消." -ForegroundColor DarkGray; ReadKey; return }
    }

    Write-Host "执行 git reset --$mode $target ..." -ForegroundColor Yellow
    git reset --$mode "$target"

    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] 回退成功!" -ForegroundColor Green
    } else {
        Write-Host "[!] 回退失败." -ForegroundColor Red
    }
    ReadKey
}

function Remove-History {
    Clear-Host
    Write-Host ("=" * 44) -ForegroundColor Cyan
    Write-Host "  删除历史提交版本" -ForegroundColor Red
    Write-Host ("=" * 44) -ForegroundColor Cyan

    Write-Host "`n提交历史:" -ForegroundColor Cyan
    git log --oneline --abbrev=8 -15

    Write-Host "`n" + ("!" * 44) -ForegroundColor Red -BackgroundColor Black
    Write-Host "  警  告" -ForegroundColor Red -BackgroundColor Black
    Write-Host "  此操作不可撤销!" -ForegroundColor Red -BackgroundColor Black
    Write-Host "  将执行 git reset --hard 永久删除指定版本之后的所有提交!" -ForegroundColor Yellow
    Write-Host "  如已推送到远程, 还需 git push --force 同步!" -ForegroundColor Yellow
    Write-Host ("!" * 44) -ForegroundColor Red -BackgroundColor Black

    $target = Read-Host "`n输入要保留的最后一个版本号 (直接回车进入历史压缩模式), 或输入 q 取消"
    if ($target -eq 'q') { ReadKey; return }

    # 空输入 → 进入历史压缩模式
    if ([string]::IsNullOrWhiteSpace($target)) {
        Write-Host "`n" + ("=" * 44) -ForegroundColor Cyan
        Write-Host "  历史压缩模式" -ForegroundColor Yellow
        Write-Host ("=" * 44) -ForegroundColor Cyan
        Write-Host "  将所有历史提交压缩为一个新提交, 保留当前文件内容" -ForegroundColor DarkGray
        Write-Host ""
        Write-Host "  [1] 以当前版本为保留版本" -ForegroundColor White
        Write-Host "      直接压缩历史, 所有旧提交将合并为一个新提交" -ForegroundColor DarkGray
        Write-Host ""
        Write-Host "  [2] 先推送再压缩 (推荐)" -ForegroundColor White
        Write-Host "      先将完整历史推送到 GitHub 备份, 再压缩本地历史" -ForegroundColor DarkGray
        Write-Host ""
        Write-Host "  [0] 取消" -ForegroundColor White

        $compressMode = Read-Host "`n请选择"
        if ($compressMode -notin '1','2') { Write-Host "已取消." -ForegroundColor DarkGray; ReadKey; return }

        $branch = git branch --show-current
        $timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'

        if ($compressMode -eq '2') {
            $remote = git remote
            if (-not $remote) {
                Write-Host "[!] 未检测到远程仓库, 无法推送" -ForegroundColor Red
                ReadKey; return
            }

            $pushConfirm = Read-Host "`n将把完整历史推送到 origin/$branch 进行备份, 确认? (y/n)"
            if ($pushConfirm -notin 'y','Y') { Write-Host "已取消." -ForegroundColor DarkGray; ReadKey; return }

            Write-Host "`n正在推送完整历史到远程..." -ForegroundColor Yellow
            git push origin "$branch"
            if ($LASTEXITCODE -ne 0) {
                Write-Host "[!] 推送失败, 操作取消" -ForegroundColor Red
                ReadKey; return
            }
            Write-Host "[OK] 推送完成, 远程已备份完整历史" -ForegroundColor Green
        }

        Write-Host "`n!!! 即将压缩本地历史 !!!" -ForegroundColor Red -BackgroundColor Black
        Write-Host "  执行后本地所有提交历史将合并为1个新提交" -ForegroundColor Yellow
        $c1 = Read-Host '请完整输入 "确认压缩" 四个字'
        if ($c1 -ne "确认压缩") { Write-Host "已取消." -ForegroundColor DarkGray; ReadKey; return }

        $c2 = Read-Host '最后确认, 输入 "yes" 执行'
        if ($c2 -ne 'yes') { Write-Host "已取消." -ForegroundColor DarkGray; ReadKey; return }

        Write-Host "`n正在创建孤立分支并压缩历史..." -ForegroundColor Yellow

        $tempBranch = "temp_clean-$timestamp"
        git checkout --orphan "$tempBranch"
        if ($LASTEXITCODE -ne 0) { Write-Host "[!] 创建孤立分支失败" -ForegroundColor Red; ReadKey; return }

        git add -A
        git commit -m "压缩历史 - $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
        if ($LASTEXITCODE -ne 0) { Write-Host "[!] 提交失败" -ForegroundColor Red; ReadKey; return }

        Write-Host "删除旧分支 $branch ..." -ForegroundColor Yellow
        git branch -D "$branch"
        git branch -m "$branch"

        Write-Host "[OK] 历史压缩成功! 所有历史已合并为1个新提交" -ForegroundColor Green

        $remote = git remote
        if ($remote) {
            $forcePush = Read-Host "`n检测到远程仓库, 是否强制推送以同步清理后的历史? (y/n)"
            if ($forcePush -in 'y','Y') {
                Write-Host "强制推送 origin/$branch ..." -ForegroundColor Yellow
                git push --force origin "$branch"
                if ($LASTEXITCODE -eq 0) {
                    Write-Host "[OK] 远程仓库已同步!" -ForegroundColor Green
                } else {
                    Write-Host "[!] 强制推送失败." -ForegroundColor Red
                }
            }
        }

        ReadKey; return
    }

    # 有输入版本号 → 原有删除流程
    $valid = git cat-file -t $target 2>$null
    if (-not $valid) { Write-Host "[!] 无效的版本号" -ForegroundColor Red; ReadKey; return }

    Write-Host "`n以下提交将被删除:" -ForegroundColor Red
    $deleteLog = git log --oneline --abbrev=8 "$target..HEAD" 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $deleteLog) {
        Write-Host "  (目标版本即为最新, 无提交可删除)" -ForegroundColor DarkGray
        ReadKey; return
    }
    $deleteLog | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }

    Write-Host "`n双重确认:" -ForegroundColor Red -BackgroundColor Black
    $c1 = Read-Host '请完整输入 "确认删除" 四个字'
    if ($c1 -ne "确认删除") { Write-Host "已取消." -ForegroundColor DarkGray; ReadKey; return }

    $c2 = Read-Host '最后确认, 输入 "yes" 执行'
    if ($c2 -ne 'yes') { Write-Host "已取消." -ForegroundColor DarkGray; ReadKey; return }

    Write-Host "`n执行 git reset --hard $target ..." -ForegroundColor Yellow
    git reset --hard "$target"

    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] 删除成功! 版本已回退到 $target" -ForegroundColor Green

        $remote = git remote
        if ($remote) {
            $forcePush = Read-Host "`n检测到远程仓库, 是否强制推送同步? (y/n)"
            if ($forcePush -in 'y','Y') {
                $branch = git branch --show-current
                Write-Host "强制推送 origin/$branch ..." -ForegroundColor Yellow
                git push --force origin "$branch"
                if ($LASTEXITCODE -eq 0) {
                    Write-Host "[OK] 远程仓库已同步!" -ForegroundColor Green
                } else {
                    Write-Host "[!] 强制推送失败." -ForegroundColor Red
                }
            }
        }
    } else {
        Write-Host "[!] 操作失败." -ForegroundColor Red
    }
    ReadKey
}

function New-Release {
    Clear-Host
    Write-Host ("=" * 44) -ForegroundColor Cyan
    Write-Host "  推送 Releases 到 GitHub" -ForegroundColor Yellow
    Write-Host ("=" * 44) -ForegroundColor Cyan

    # ====== 1. 检测 gh CLI ======
    $ghPath = Get-Command gh -ErrorAction SilentlyContinue
    if (-not $ghPath) {
        Write-Host "`n[!] 未找到 GitHub CLI (gh), 请先安装:" -ForegroundColor Red
        Write-Host "  winget install --id GitHub.cli" -ForegroundColor Yellow
        ReadKey; return
    }

    # ====== 2. 检查 gh 认证 ======
    $null = gh auth status 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "`n[!] GitHub CLI 未登录, 请先运行 gh auth login" -ForegroundColor Red
        ReadKey; return
    }

    # ====== 3. 处理未提交更改 ======
    $status = git status --porcelain
    if ($status) {
        Write-Host "`n检测到未提交的更改:" -ForegroundColor Yellow
        git status --short
        $choice = Read-Host "`n是否先提交所有更改? (y/n/q取消)"
        if ($choice -eq 'q') { return }
        if ($choice -in 'y','Y') {
            $msg = Read-Host "请输入提交信息"
            if ([string]::IsNullOrWhiteSpace($msg)) { $msg = "更新 $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" }
            git add -A
            git commit -m "$msg"
            if ($LASTEXITCODE -ne 0) { Write-Host "[!] 提交失败" -ForegroundColor Red; ReadKey; return }
            Write-Host "[OK] 提交完成" -ForegroundColor Green
        } else {
            Write-Host "[!] 请先提交或暂存更改后再创建 Release" -ForegroundColor Yellow
            ReadKey; return
        }
    }

    # ====== 4. 自动检测版本号 ======
    $tags = git tag --sort=-v:refname | Where-Object { $_ -match '^v(\d+)\.(\d+)\.(\d+)$' }
    $latestVersion = $null
    $latestMajor = 1; $latestMinor = 0; $latestPatch = 0

    if ($tags) {
        $latestTag = $tags | Select-Object -First 1
        if ($latestTag -match '^v(\d+)\.(\d+)\.(\d+)$') {
            $latestMajor = [int]$Matches[1]
            $latestMinor = [int]$Matches[2]
            $latestPatch = [int]$Matches[3]
            $latestVersion = $latestTag
        }
    }

    Write-Host "`n当前最新版本: " -ForegroundColor Cyan -NoNewline
    if ($latestVersion) {
        Write-Host "$latestVersion" -ForegroundColor Green
    } else {
        Write-Host "(无版本标签)" -ForegroundColor DarkGray
    }

    # ====== 5. 选择版本递增方式 ======
    Write-Host "`n版本递增方式:" -ForegroundColor Cyan
    Write-Host ("  [1] 小版本更新 (v{0}.{1}.0)" -f $latestMajor, ($latestMinor + 1)) -ForegroundColor White
    Write-Host "      适用于新增功能 (默认)" -ForegroundColor DarkGray
    Write-Host ("  [2] 补丁更新 (v{0}.{1}.{2})" -f $latestMajor, $latestMinor, ($latestPatch + 1)) -ForegroundColor White
    Write-Host "      适用于 Bug 修复" -ForegroundColor DarkGray
    Write-Host ("  [3] 大版本更新 (v{0}.0.0)" -f ($latestMajor + 1)) -ForegroundColor White
    Write-Host "      适用于重大变更" -ForegroundColor DarkGray
    Write-Host "  [4] 自定义版本号" -ForegroundColor White

    $bumpChoice = Read-Host "`n请选择 (默认 1)"
    if ([string]::IsNullOrWhiteSpace($bumpChoice)) { $bumpChoice = '1' }

    $newMajor = $latestMajor; $newMinor = $latestMinor; $newPatch = $latestPatch
    switch ($bumpChoice) {
        '1' { $newMinor++; $newPatch = 0 }
        '2' { $newPatch++ }
        '3' { $newMajor++; $newMinor = 0; $newPatch = 0 }
        '4' {
            do {
                $customVer = Read-Host "`n输入完整版本号 (格式: x.y.z)"
                $valid = $customVer -match '^\d+\.\d+\.\d+$'
                if (-not $valid) { Write-Host "[!] 格式错误, 请使用 x.y.z 格式 (如 2.0.0)" -ForegroundColor Red }
            } until ($valid)
            $parts = $customVer -split '\.'
            $newMajor = [int]$parts[0]; $newMinor = [int]$parts[1]; $newPatch = [int]$parts[2]
        }
        default { $newMinor++; $newPatch = 0 }
    }

    $newTag = "v$newMajor.$newMinor.$newPatch"

    # ====== 6. 检查标签是否已存在 ======
    $existing = git tag -l "$newTag"
    if ($existing) {
        Write-Host "`n[!] 标签 $newTag 已存在!" -ForegroundColor Red
        $overwrite = Read-Host "是否强制覆盖? (y/n)"
        if ($overwrite -in 'y','Y') {
            git tag -d "$newTag"
            git push origin --delete "$newTag" 2>$null
        } else {
            Write-Host "已取消." -ForegroundColor DarkGray
            ReadKey; return
        }
    }

    Write-Host "`n新版本号: " -ForegroundColor Cyan -NoNewline
    Write-Host "$newTag" -ForegroundColor Green -BackgroundColor Black

    # ====== 7. 生成 Release 描述 ======
    Write-Host "`n--- Release 描述 ---" -ForegroundColor Cyan

    # 自动收集自上个版本以来的提交日志 (使用 --encoding=utf-8 避免中文乱码)
    if ($latestVersion) {
        $commitLog = git -c i18n.logOutputEncoding=utf-8 log --oneline --abbrev=8 "$latestVersion..HEAD" 2>$null
    } else {
        $commitLog = git -c i18n.logOutputEncoding=utf-8 log --oneline --abbrev=8 2>$null
    }

    Write-Host "`n自上一版本以来的提交记录:" -ForegroundColor DarkGray
    if ($commitLog) {
        $commitLog -split "`n" | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
    } else {
        Write-Host "  (无新提交)" -ForegroundColor DarkGray
    }

    # 生成建议描述
    $suggestedDesc = @()
    $suggestedDesc += "## 更新内容"
    if ($commitLog) {
        foreach ($line in ($commitLog -split "`n")) {
            $trimmed = $line.Trim()
            if ($trimmed) {
                # 去掉提交哈希前缀
                $msg = $trimmed -replace '^[a-f0-9]+\s+', ''
                $suggestedDesc += "- $msg"
            }
        }
    }
    $defaultDesc = $suggestedDesc -join "`n"

    Write-Host "`nRelease 描述:" -ForegroundColor Yellow
    Write-Host "  直接回车 = 使用自动生成的内容" -ForegroundColor DarkGray
    Write-Host "  输入 +d 并回车 = 使用自动生成并继续编辑" -ForegroundColor DarkGray
    Write-Host "  其他输入 = 手动逐行输入" -ForegroundColor DarkGray
    Write-Host "  (输入 --- 单独一行结束)" -ForegroundColor DarkGray
    Write-Host ""

    $descChoice = Read-Host "请选择 (回车默认 / +d 编辑 / 手动输入)"

    $releaseNotes = ""
    if ([string]::IsNullOrWhiteSpace($descChoice)) {
        # 使用自动生成
        $releaseNotes = $defaultDesc
    } elseif ($descChoice -eq '+d') {
        # 自动生成后允许编辑
        Write-Host "`n请在下面输入描述 (输入 --- 单独一行结束):" -ForegroundColor Yellow
        Write-Host $defaultDesc -ForegroundColor DarkGray
        $lines = @()
        while ($true) {
            $line = Read-Host
            if ($line -eq '---') { break }
            $lines += $line
        }
        if ($lines.Count -gt 0) {
            $releaseNotes = $lines -join "`n"
        } else {
            $releaseNotes = $defaultDesc
        }
    } else {
        # 手动输入
        Write-Host "`n请逐行输入描述 (输入 --- 单独一行结束):" -ForegroundColor Yellow
        $lines = @($descChoice)
        while ($true) {
            $line = Read-Host
            if ($line -eq '---') { break }
            $lines += $line
        }
        $releaseNotes = $lines -join "`n"
    }

    # ====== 8. Release 预览 ======
    $branch = git branch --show-current
    Write-Host "`n" ("=" * 44) -ForegroundColor Cyan
    Write-Host "  Release 预览" -ForegroundColor Green
    Write-Host ("=" * 44) -ForegroundColor Cyan
    Write-Host "  标签: " -NoNewline; Write-Host "$newTag" -ForegroundColor Green
    Write-Host "  目标: " -NoNewline; Write-Host "$branch" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  描述:" -ForegroundColor Cyan
    $releaseNotes -split "`n" | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
    Write-Host ""

    # ====== 9. 确认并推送当前分支 ======
    $confirm = Read-Host "确认创建并推送 Release $newTag ? (y/n)"
    if ($confirm -notin 'y','Y') { Write-Host "已取消." -ForegroundColor DarkGray; ReadKey; return }

    Write-Host "`n[1/3] 推送到 origin/$branch ..." -ForegroundColor Yellow
    git push origin "$branch"
    if ($LASTEXITCODE -ne 0) { Write-Host "[!] 推送失败" -ForegroundColor Red; ReadKey; return }
    Write-Host "  [OK] 推送成功" -ForegroundColor Green

    # ====== 10. 创建并推送标签 ======
    Write-Host "[2/3] 创建标签 $newTag ..." -ForegroundColor Yellow
    git tag -a "$newTag" -m "Release $newTag"
    if ($LASTEXITCODE -ne 0) { Write-Host "[!] 创建标签失败" -ForegroundColor Red; ReadKey; return }
    Write-Host "  [OK] 标签已创建" -ForegroundColor Green

    Write-Host "  推送标签到远程..." -ForegroundColor Yellow
    git push origin "$newTag"
    if ($LASTEXITCODE -ne 0) { Write-Host "[!] 推送标签失败" -ForegroundColor Red; ReadKey; return }
    Write-Host "  [OK] 标签推送成功" -ForegroundColor Green

    # ====== 11. 创建 GitHub Release ======
    Write-Host "[3/3] 创建 GitHub Release ..." -ForegroundColor Yellow

    # 将描述写入临时文件 (避免 shell 转义问题)
    $tempFile = [System.IO.Path]::GetTempFileName()
    try {
        $releaseNotes | Out-File -FilePath $tempFile -Encoding utf8
        gh release create "$newTag" --title "$newTag" --notes-file "$tempFile" --target "$branch"
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  [OK] GitHub Release 创建成功!" -ForegroundColor Green
            $repoUrl = gh repo view --json url -q .url 2>$null
            if ($repoUrl) {
                Write-Host "  Release 地址: " -ForegroundColor Cyan -NoNewline
                Write-Host "$repoUrl/releases/tag/$newTag" -ForegroundColor Blue
            }
        } else {
            Write-Host "  [!] 创建 Release 失败, 但标签已推送" -ForegroundColor Red
            Write-Host "  可手动运行: gh release create $newTag --title `"$newTag`"" -ForegroundColor Yellow
        }
    } finally {
        if (Test-Path $tempFile) { Remove-Item $tempFile -Force }
    }

    Write-Host "`n" ("=" * 44) -ForegroundColor Cyan
    Write-Host "  Release $newTag 已完成!" -ForegroundColor Green
    ReadKey
}

function Build-Project {
    Clear-Host
    Write-Host ("=" * 44) -ForegroundColor Cyan
    Write-Host "  构建与打包" -ForegroundColor Green
    Write-Host ("=" * 44) -ForegroundColor Cyan

    Write-Host "`nAuto Shutdown (Python/PySide6)" -ForegroundColor DarkGray

    Write-Host "`n  [1] 开发运行 (python main.py)" -ForegroundColor White
    Write-Host "  [2] 打包为单文件 exe" -ForegroundColor White
    Write-Host "  [3] 清理 build/dist 目录" -ForegroundColor White
    Write-Host "  [4] 清理后通过 spec 打包" -ForegroundColor White
    Write-Host "  [5] 安装依赖 (pip install -r requirements.txt)" -ForegroundColor White
    Write-Host "  [0] 返回主菜单" -ForegroundColor White

    $choice = Read-Host "`n请选择"

    # 确保在项目根目录
    $projectRoot = $PSScriptRoot
    Set-Location $projectRoot

    switch ($choice) {
        '1' {
            Write-Host "`n启动 Auto Shutdown (开发模式)..." -ForegroundColor Yellow
            python main.py
            Write-Host "`n应用已退出。" -ForegroundColor DarkGray
        }
        '2' {
            Write-Host "`n检查虚拟环境..." -ForegroundColor Yellow
            if (Test-Path ".venv/Scripts/Activate.ps1") {
                & ".venv/Scripts/Activate.ps1"
            }
            Write-Host "正在打包为单文件 exe ..." -ForegroundColor Yellow
            python build_exe.py
            if ($LASTEXITCODE -eq 0) {
                Write-Host "[OK] 打包完成! exe 文件位于 dist/ 目录" -ForegroundColor Green
            } else {
                Write-Host "[!] 打包失败, 可尝试选项 4" -ForegroundColor Red
            }
        }
        '3' {
            Write-Host "`n清理 build 和 dist 目录..." -ForegroundColor Yellow
            if (Test-Path "build") { Remove-Item -Recurse -Force "build"; Write-Host "  build/ 已删除" -ForegroundColor Gray }
            if (Test-Path "dist") { Remove-Item -Recurse -Force "dist"; Write-Host "  dist/ 已删除" -ForegroundColor Gray }
            if (Test-Path *.spec) { Remove-Item -Force *.spec -ErrorAction SilentlyContinue; Write-Host "  .spec 文件已删除" -ForegroundColor Gray }
            Write-Host "[OK] 清理完成" -ForegroundColor Green
        }
        '4' {
            Write-Host "`n先清理旧构建文件..." -ForegroundColor Yellow
            if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
            if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
            Write-Host "通过 AutoShutdownHelper.spec 打包..." -ForegroundColor Yellow
            python -m PyInstaller AutoShutdownHelper.spec
            if ($LASTEXITCODE -eq 0) {
                Write-Host "[OK] 打包完成!" -ForegroundColor Green
            } else {
                Write-Host "[!] 打包失败" -ForegroundColor Red
            }
        }
        '5' {
            Write-Host "`n安装依赖..." -ForegroundColor Yellow
            if (Test-Path ".venv/Scripts/Activate.ps1") {
                & ".venv/Scripts/Activate.ps1"
            }
            pip install -r requirements.txt
            if ($LASTEXITCODE -eq 0) {
                Write-Host "[OK] 依赖安装完成" -ForegroundColor Green
            } else {
                Write-Host "[!] 安装失败" -ForegroundColor Red
            }
        }
        '0' { return }
        default { Write-Host "[!] 无效选项" -ForegroundColor Red }
    }
    ReadKey
}


# ====== 主循环 ======
do {
    Show-Menu
    $choice = Read-Host "请输入选项"
    switch ($choice) {
        '1' { Push-ToGitHub }
        '2' { Update-FromGitHub }
        '3' { Show-Status }
        '4' { Show-BranchMenu }
        '5' { Reset-Version }
        '6' { Remove-History }
        '7' { Build-Project }
        '8' { New-Release }
        '0' { Write-Host "`n再见!" -ForegroundColor Green; break }
        default { Write-Host "[!] 无效选项" -ForegroundColor Red; Start-Sleep -Seconds 1 }
    }
} while ($choice -ne '0')
