# SSH_brute
SSH brute password discovery
This code has been tested on Ubuntu 22.04.
You need to make sure all these apps and packages are installed on your Ubuntu server.

sudo apt update
sudo apt install python3 python3-pip python3-dev -y
apt install python3-paramiko
pip3 install paramiko
sudo apt install libffi-dev libssl-dev -y
python3 --version
pip3 show paramiko

nano ssh_brute.py
# [Paste the script content and save with Ctrl+X, Y, Enter]
chmod +x ssh_brute.py

# For monitoring network connections
sudo apt install net-tools
# For better terminal experience
sudo apt install tmux 

# all commands at one line:
sudo apt update && sudo apt upgrade -y && sudo apt install python3 python3-pip python3-dev libffi-dev libssl-dev python3-venv -y && pip3 install paramiko && python3 -m venv sshbrute-env && source sshbrute-env/bin/activate


# Using screen
sudo apt install screen
screen -S sshbrute
./ssh_brute.py target_ip_address username password_length --lower --upper --digits --special '!@#$'
# Detach with Ctrl+A, D

# Or using tmux
tmux new -s sshbrute
./ssh_brute.py target_ip_address username password_length --lower --upper --digits --special '!@#$'
# Detach with Ctrl+B, D

# or if you run it in the existing session just use this command when you are in the folder that the script is there.
./ssh_brute.py target_ip_address username password_length --lower --upper --digits --special '!@#$'
