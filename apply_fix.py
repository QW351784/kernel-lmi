import pathlib, sys

tag, asset = sys.argv[1], sys.argv[2]
wf = pathlib.Path('.github/workflows/build.yml')
s = wf.read_text(encoding='utf-8')
changed = []

# 1) thin 分支补 CFI/SCS 关闭
thin_old = """            thin)
              sed -i '/^CONFIG_THINLTO=y/d' $DEF
              echo "CONFIG_THINLTO=y" >> $DEF
              ;;
"""
thin_new = """            thin)
              sed -i '/^CONFIG_THINLTO=y/d' $DEF
              echo "CONFIG_THINLTO=y" >> $DEF
              sed -i 's/^CONFIG_CFI_CLANG=y/# CONFIG_CFI_CLANG is not set/' $DEF
              sed -i 's/^CONFIG_SHADOW_CALL_STACK=y/# CONFIG_SHADOW_CALL_STACK is not set/' $DEF
              ;;
"""
if "CONFIG_CFI_CLANG is not set" not in thin_old:
    pass
if thin_old in s:
    s = s.replace(thin_old, thin_new, 1)
    changed.append("thin 分支关 CFI/SCS")

# 2) JOBS 4 -> 2
if "      JOBS: 4\n" in s:
    s = s.replace("      JOBS: 4\n", "      JOBS: 2\n", 1)
    changed.append("JOBS 4->2")

# 3) 编译日志 tee
if "          ./build.sh > /tmp/build_all.log 2>&1 || {\n" in s:
    s = s.replace("          ./build.sh > /tmp/build_all.log 2>&1 || {\n",
                  "          ./build.sh 2>&1 | tee /tmp/build_all.log || {\n", 1)
    changed.append("日志 tee（保留错误摘要）")
elif "          ./build.sh 2>&1 | tail -100\n" in s:
    s = s.replace("          ./build.sh 2>&1 | tail -100\n",
                  "          ./build.sh 2>&1 | tee /tmp/build_all.log\n", 1)
    changed.append("日志 tee（去掉 tail 截断）")

# 4) 插入 Inject 步骤
if "name: Inject Install Screen Text" not in s:
    inject = pathlib.Path('inject_block.txt').read_text(encoding='utf-8')
    anchor = "      - name: Verify Artifacts\n"
    assert anchor in s, "Verify 锚点缺失"
    s = s.replace(anchor, inject + "\n" + anchor, 1)
    changed.append("插入刷入界面注入步骤")

# 5) Publish 覆盖
start = s.index("      - name: Publish Release")
s = s[:start] + f"""      - name: Publish Release
        env:
          GH_TOKEN: ${{{{ secrets.GITHUB_TOKEN }}}}
        run: |
          set -e
          cd kernel
          ZIP=$(ls out/*.zip | head -1)
          REL=$(cat out/include/config/kernel.release)
          echo "uname: $REL / device: lmi / variant: $VARIANT / lto: $LTO_MODE"
          echo "=== 直接覆盖 {tag} 的正式资产，不新建 tag ==="
          REL_ID=$(curl -s -H "Authorization: token $GH_TOKEN" \\
            "https://api.github.com/repos/$GITHUB_REPOSITORY/releases/tags/{tag}" \\
            | python3 -c "import json,sys;print(json.load(sys.stdin)['id'])")
          echo "release id: $REL_ID"
          for AID in $(curl -s -H "Authorization: token $GH_TOKEN" \\
            "https://api.github.com/repos/$GITHUB_REPOSITORY/releases/$REL_ID/assets" \\
            | python3 -c "import json,sys;print(' '.join(str(a['id']) for a in json.load(sys.stdin)))"); do
            echo "删旧资产 $AID"
            curl -s -o /dev/null -X DELETE -H "Authorization: token $GH_TOKEN" \\
              "https://api.github.com/repos/$GITHUB_REPOSITORY/releases/assets/$AID"
          done
          echo "上传新包并命名 {asset}"
          curl -sS -X POST \\
            -H "Authorization: token $GH_TOKEN" \\
            -H "Content-Type: application/zip" \\
            --data-binary @"$ZIP" \\
            "https://uploads.github.com/repos/$GITHUB_REPOSITORY/releases/$REL_ID/assets?name={asset}" \\
            | python3 -c "import json,sys;d=json.load(sys.stdin);print('上传完成:', d.get('name'), d.get('size'), 'B')"
"""
changed.append(f"Publish 覆盖 {tag}")

wf.write_text(s, encoding='utf-8')
print("改动:", " / ".join(changed))
