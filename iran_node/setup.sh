#!/data/data/com.termux/files/usr/bin/sh
# Sets up the Iran-side node on the owner's phone in Termux (SP_D_HANDOFF.md section 30).
# Safe to run again. After `git pull` in ~/gold-premium-monitor:  sh iran_node/setup.sh

NODE="$HOME/gold-premium-monitor/iran_node/node.py"

echo "1/5 packages"
command -v crond >/dev/null 2>&1 || pkg install -y cronie >/dev/null 2>&1
python -c "import requests" 2>/dev/null || pip install -q requests
python -c "import bs4" 2>/dev/null || pip install -q beautifulsoup4
command -v crond >/dev/null 2>&1 && echo "    ok" || echo "    cronie missing: run 'pkg update' and this script again"

echo "2/5 keep running when the screen is off"
termux-wake-lock 2>/dev/null && echo "    ok (a Termux notification shows the wake lock)"

echo "3/5 start again after a reboot (needs the Termux:Boot app, opened once)"
mkdir -p "$HOME/.termux/boot"
printf '%s\n' "#!/data/data/com.termux/files/usr/bin/sh" "termux-wake-lock" "crond" > "$HOME/.termux/boot/start-node"
chmod +x "$HOME/.termux/boot/start-node"
echo "    ok"

echo "4/5 every 15 minutes"
echo "*/15 * * * * $PREFIX/bin/python $NODE >/dev/null 2>&1" | crontab -
crontab -l | sed 's/^/    /'
pgrep -x crond >/dev/null 2>&1 || crond
pgrep -x crond >/dev/null 2>&1 && echo "    scheduler running" || echo "    scheduler NOT running"

echo "5/5 one reading now"
python "$NODE"

echo "done. To check later:  tail -3 ~/iran_node.log"
