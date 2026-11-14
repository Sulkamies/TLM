# Training the floor-plan detector on Verda: step by step

You work in **two places**:
- **PowerShell on your laptop**, in `C:\Users\sakke\Documents\TLM\TLM`
- **a terminal on the Verda GPU machine** (VM), reached over SSH

Billing:
- The VM is billed from the moment you deploy it until you **delete** it. A shut-down VM still costs the full GPU price.
- Plan for about 3–4 hours of VM time in total, and delete the VM when you're done (step 13).

Placeholders used below:
- `<IP>` is the VM's public IP address.
- `root` is the login user. If the Verda console shows a different SSH user, use that one everywhere instead.

---

## Part A: Get a GPU machine (laptop + browser, ~15 min)

**1. Claim the credits.** Sign up at the Verda console, submit the Junction credit form, and follow
Verda's docs to redeem the credits. Check that the balance shows up in the console before deploying anything.

**2. Create an SSH key** (PowerShell; OpenSSH is built into Windows 10/11):
```powershell
ssh-keygen -t ed25519 -C "junction-verda"
```
Press Enter to accept the default location. A passphrase is optional. Then print the public key:
```powershell
Get-Content $HOME\.ssh\id_ed25519.pub
```
Copy the whole line (`ssh-ed25519 AAAA... junction-verda`). In the Verda console, go to **Keys → SSH Keys → Create**,
paste it and save.

**3. Deploy the instance.** In the console, go to **Instances → Deploy Instance**:
- **Contract: On-demand.** Not spot: spot machines can be taken away in the middle of training.
- **GPU: 1× H100 or 1× A100 (80 GB)**, whichever is available. An L40S (48 GB) also works, but use `--batch 8`. Check the hourly price against your credits.
- **Location:** any. FIN-01 is in Finland.
- **OS image:** Ubuntu 24.04 with CUDA (the variant with Docker is fine too).
- **Storage: OS volume of at least 150 GB.** The dataset, its unzipped copy, the converted copy and PyTorch need about 30 GB together, and the rest is headroom.
- **SSH key:** select the key from step 2.
- **Hostname:** `cubicasa-train`.

Click **Deploy now**, wait until the instance shows as running, and copy its **IP address**.

**4. Connect** (PowerShell):
```powershell
ssh root@<IP>
```
Type `yes` the first time. Your prompt changes to something like `root@cubicasa-train:~#`, which means you're on the VM.
Check the GPU:
```bash
nvidia-smi
```

## Part B: Upload code and data (laptop, ~5 min)

**5.** Open a **second** PowerShell window (keep the SSH one open):
```powershell
cd "C:\Users\sakke\Documents\TLM\TLM"
scp -r blueprints-starter root@<IP>:~/
scp -r "C:\Users\sakke\Documents\Junction 2026\junction-dataset-preview\data\cubicasa5k" root@<IP>:~/plans
```
The first command uploads the code. The second uploads the 241 question images (about 100 MB), which get pre-analysed at the end.

## Part C: Set up and convert (VM, ~20 min)

**6. Install everything and download CubiCasa5K** (about 10 minutes):
```bash
cd ~/blueprints-starter
bash train/setup_vm.sh
source ~/venv/bin/activate
```
It should end with `CUDA available: True` and the GPU name. If it fails with `$'\r': command not found`,
run `sed -i 's/\r$//' train/setup_vm.sh` and try again.

`source ~/venv/bin/activate` is needed again every time you open a new SSH session.

**7. List the label names** in the dataset:
```bash
python train/cubicasa_to_yolo.py --src ~/data --discover
```
- It should print `found ~5000 plans`, then each label name with what it maps to.
- Look for names ending in `-> None` that should be a window, door, toilet, sink, bathtub, shower or sauna bench.
- Fix them in `CLASS_RULES` in `train/cubicasa_to_yolo.py`: edit the file on your laptop, upload it again
  (`scp blueprints-starter\train\cubicasa_to_yolo.py root@<IP>:~/blueprints-starter/train/`), and rerun.
  Or paste the list to Claude.
- If it prints `found 0 plans`, run `ls -R ~/data | head -30` and share the output.

**8. Convert the labels** (leaves out the 241 question images):
```bash
python train/cubicasa_to_yolo.py --src ~/data --out ~/yolo --exclude train/exclude_ids.txt
```
At the end it prints counts: roughly 4,300 train, 450 val, 241 excluded, plus boxes per class. A class with 0 boxes
means a mapping problem, so go back to step 7.

## Part D: Train (VM, 1–3 h)

**9. Smoke test** (1 epoch, about 10 minutes):
```bash
python train/train.py --data ~/yolo/data.yaml --epochs 1 --name smoke
```
Download the preview image on your laptop and open it:
```powershell
scp root@<IP>:~/runs/smoke/train_batch0.jpg .
```
The boxes must sit exactly on windows, toilets and so on. If they're shifted or the wrong size, the coordinate scaling
is off: rerun step 8 with `--image F1_original.png` added, and repeat the smoke test.

**10. Full training inside `tmux`,** so it keeps running if your SSH connection drops:
```bash
tmux new -s train
source ~/venv/bin/activate && cd ~/blueprints-starter
python train/train.py --data ~/yolo/data.yaml --name cubicasa_v1
```
- To leave it running, press **Ctrl+B, then D**. You can close the laptop; to come back: `ssh root@<IP>`, then `tmux attach -t train`.
- If you get "CUDA out of memory", stop it (Ctrl+C) and rerun with `--batch 8`.
- It stops early once accuracy stops improving.
- At the end it prints mAP50 per class. Doors, windows and toilets should be high. If small fixtures are weak, a second
  run with `--imgsz 1600 --name cubicasa_v2` usually helps.

**11. Pre-analyse the question images** with the trained model:
```bash
cd ~/blueprints-starter
python -m vision.analyze --weights ~/runs/cubicasa_v1/weights/best.pt --folder ~/plans --out ~/cache/vision
```
This takes a few minutes on the GPU and writes one JSON file per image.

## Part E: Bring results home and stop paying

**12. Download** (laptop, in `C:\Users\sakke\Documents\TLM\TLM`):
```powershell
mkdir blueprints-starter\models, blueprints-starter\cache -Force
scp root@<IP>:~/runs/cubicasa_v1/weights/best.pt blueprints-starter\models\cubicasa_v1.pt
scp -r root@<IP>:~/cache/vision blueprints-starter\cache\
scp root@<IP>:~/runs/cubicasa_v1/results.png .
scp root@<IP>:~/runs/cubicasa_v1/confusion_matrix.png .
```
Check that `models\cubicasa_v1.pt` exists and that `cache\vision` holds about 241 `.json` files.

**13. Delete the VM.** In the console, go to **Instances → (your instance) → Delete** and **tick the OS volume for deletion**
as well (storage you keep is billed separately). Shutting down is not enough.

## Part F: Use the model on your laptop

**14.** In your activated `.venv`:
```powershell
cd blueprints-starter
pip install -r requirements.txt
python -c "from handlers.raster import RasterPlan; p = RasterPlan(r'C:\Users\sakke\Documents\Junction 2026\junction-dataset-preview\data\cubicasa5k\colorful-11397.png'); print(p.summary())"
```
- For question images, this reads `cache/vision/colorful-11397.png.json`.
- For any new image, it runs the model on your CPU (a few seconds; the first run also downloads the OCR model) and caches the result.
- The weights path defaults to `models/cubicasa_v1.pt` and can be changed with the `BP_WEIGHTS` environment variable.
- For the expected answers to compare with, look up `colorful-11397` in the questions file: 13 windows, 2 WC seats.

**15. Commit** (the weights and cache are excluded by `.gitignore`):
```powershell
cd "C:\Users\sakke\Documents\TLM\TLM"
git add .gitignore blueprints-starter
git commit -m "[A3] Train CubiCasa detector on Verda GPU VM"
git push -u origin a3/SS/cubicasa-detector
```
Share `best.pt` with the team outside git (e.g. a shared drive or IronShard).
