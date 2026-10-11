from flask import Flask, render_template, request, jsonify
from pathlib import Path
import os, re, zipfile, tempfile, shutil, subprocess, urllib.parse, json, urllib.request, urllib.error

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 35 * 1024 * 1024  # 35 MB request cap
MAX_FILES = 2500
MAX_UNPACKED = 100 * 1024 * 1024
ALLOWED_SOURCE = {".py",".js",".jsx",".ts",".tsx",".java",".c",".h",".cpp",".cs",".go",".rs",".php",".rb",".swift",".kt",".html",".css",".scss",".sql",".sh",".yml",".yaml",".toml",".ini",".json",".xml",".md",".txt",".env.example",".dockerfile"}
SKIP_DIRS = {".git","node_modules","vendor","dist","build",".venv","venv","__pycache__","coverage"}

def language_for(path):
    ext = Path(path).suffix.lower()
    return {".py":"Python",".js":"JavaScript",".jsx":"React/JSX",".ts":"TypeScript",".tsx":"React/TSX",".java":"Java",".c":"C",".h":"C/C++ header",".cpp":"C++",".cs":"C#",".go":"Go",".rs":"Rust",".php":"PHP",".rb":"Ruby",".swift":"Swift",".kt":"Kotlin",".html":"HTML",".css":"CSS",".scss":"SCSS",".sql":"SQL",".sh":"Shell",".yml":"YAML",".yaml":"YAML",".toml":"TOML",".json":"JSON",".xml":"XML",".md":"Markdown"}.get(ext, "Other")

def safe_files(root):
    found=[]
    for p in Path(root).rglob("*"):
        if any(part in SKIP_DIRS for part in p.parts): continue
        if not p.is_file(): continue
        try: rel=p.relative_to(root).as_posix()
        except ValueError: continue
        if p.suffix.lower() in ALLOWED_SOURCE or p.name.lower() in {"dockerfile","makefile","requirements.txt","package.json","pom.xml","go.mod","cargo.toml"}:
            found.append((p,rel))
            if len(found)>=MAX_FILES: break
    return found

def analyze_tree(root, source_label):
    files=safe_files(root)
    if not files:
        return {"error":"No supported source/configuration files were found. Upload a ZIP or source file containing code."}, 400
    findings=[]; languages={}; inventory=[]; total_lines=0; source_count=0
    tests=0; docs=False; deps=False; total_bytes=0
    rules=[
      ("Hardcoded secret pattern","HIGH",re.compile(r'(?i)(api[_-]?key|secret|password|token|private[_-]?key)\s*[:=]\s*[\'"][^\'"\s]{8,}[\'"]'),"Move credentials to environment variables or a secret manager. Rotate any real exposed credential."),
      ("Potential unsafe dynamic evaluation","HIGH",re.compile(r'\b(eval|exec)\s*\('),"Avoid evaluating untrusted strings. Replace dynamic execution with explicit parsing or safe dispatch."),
      ("Potential SQL injection pattern","HIGH",re.compile(r'(?i)(execute|query)\s*\(\s*[\'"][^\'"]*%s|execute\s*\(\s*f[\'"]|query\s*\(\s*[`"][^`"]*\$\{'),"Use parameterized queries / prepared statements; never concatenate untrusted input into SQL."),
      ("Debug mode enabled","MEDIUM",re.compile(r'(?i)(debug\s*=\s*True|DEBUG\s*=\s*true|app\.run\([^)]*debug\s*=\s*True)'),"Disable debug mode in production and configure errors/logging safely."),
      ("Broad exception handling","LOW",re.compile(r'except\s*:\s*$|catch\s*\(\s*[^)]*\)\s*\{\s*\}'),"Catch specific exceptions and log actionable context; avoid swallowing failures."),
      ("TODO / FIXME marker","LOW",re.compile(r'\b(TODO|FIXME|XXX)\b'),"Review this unfinished marker; turn it into a tracked task or remove it when resolved.")
    ]
    for p,rel in files:
        ext=p.suffix.lower(); lang=language_for(rel); languages[lang]=languages.get(lang,0)+1
        low=rel.lower()
        if "test" in low or "spec" in low: tests+=1
        if Path(rel).name.lower() in {"readme.md","readme.rst","readme.txt"}: docs=True
        if Path(rel).name.lower() in {"requirements.txt","package.json","package-lock.json","pyproject.toml","poetry.lock","pom.xml","go.mod","cargo.toml","gemfile"}: deps=True
        try:
            size=p.stat().st_size; total_bytes+=size
            if size>1_500_000: continue
            raw=p.read_text(encoding="utf-8",errors="replace")
        except (OSError, UnicodeError): continue
        lines=raw.splitlines(); total_lines+=len(lines)
        inventory.append({"path":rel,"language":lang,"lines":len(lines),"bytes":size,"risk":"LOW"})
        for title,sev,pat,fix in rules:
            for idx,line in enumerate(lines,1):
                if pat.search(line):
                    # Avoid exposing matched secret values in the report.
                    evidence=re.sub(r'(?i)(api[_-]?key|secret|password|token|private[_-]?key)(\s*[:=]\s*)[\'"][^\'"]+[\'"]',r'\1\2"[REDACTED]"',line.strip())[:220]
                    findings.append({"agent":"Static Rule Scanner","severity":sev,"title":title,"file":rel,"line":idx,"evidence":evidence or "Pattern matched on this line","fix":fix,"id":f"{rel}:{idx}:{title}"})
                    if sev in ("HIGH","MEDIUM"):
                        for item in inventory:
                            if item["path"]==rel: item["risk"]="HIGH" if sev=="HIGH" else "MEDIUM"
                    if len(findings)>=150: break
                if len(findings)>=150: break
            if len(findings)>=150: break
        if len(findings)>=150: break
    if not docs:
        findings.append({"agent":"Project Structure Agent","severity":"LOW","title":"README documentation not found","file":"README.md","line":1,"evidence":"No common README file was detected at the scanned project root.","fix":"Add setup instructions, prerequisites, configuration, tests, and deployment notes.","id":"missing-readme"})
    if not tests:
        findings.append({"agent":"Test Readiness Agent","severity":"MEDIUM","title":"Test files not detected","file":"tests/","line":1,"evidence":"No paths containing test or spec were found in the scanned file inventory.","fix":"Add unit tests for core logic and regression tests for important bug fixes.","id":"missing-tests"})
    if not deps:
        findings.append({"agent":"Dependency Agent","severity":"LOW","title":"Dependency manifest not detected","file":"project root","line":1,"evidence":"No common dependency manifest was detected.","fix":"Declare dependencies and versions in a standard manifest for repeatable builds.","id":"missing-dependencies"})
    counts={s:sum(1 for f in findings if f["severity"]==s) for s in ["HIGH","MEDIUM","LOW"]}
    # Transparent heuristic, capped to avoid misleading scores from a single rule family.
    penalty=min(55, counts["HIGH"]*13 + counts["MEDIUM"]*6 + counts["LOW"]*2)
    score=max(0,100-penalty)
    if total_lines==0: score=max(0,score-10)
    summary={"health":score,"files":len(files),"lines":total_lines,"findings":findings,"counts":counts,"languages":languages,"inventory":sorted(inventory,key=lambda x:({"HIGH":0,"MEDIUM":1,"LOW":2}.get(x["risk"],3),-x["lines"]))[:120],"source":source_label,"agents":[["Project Ingestion","Complete"],["Static Rule Scanner","Complete"],["Secret Pattern Review","Complete"],["Test Readiness Agent","Complete"],["Dependency Agent","Complete"],["Documentation Agent","Complete"],["Repair Planner","Ready"],["Fix Verification","Manual review required"]],"limits":{"files":MAX_FILES,"size_mb":35}}
    return summary,200

def validate_github_url(url):
    try:
        u=urllib.parse.urlparse(url.strip())
        if u.scheme!="https" or u.netloc.lower() not in {"github.com","www.github.com"}: return None
        bits=[x for x in u.path.strip("/").split("/") if x]
        if len(bits)<2 or any(x in {".",".."} for x in bits): return None
        owner,repo=bits[0],bits[1].removesuffix(".git")
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}",owner) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}",repo): return None
        return f"https://github.com/{owner}/{repo}.git", f"{owner}/{repo}"
    except Exception: return None

@app.get("/healthz")
def healthz():
    return jsonify({"status":"ok","service":"RepoGuardian X","version":"1.0.0"})

@app.get("/api/config")
def public_config():
    # Supabase anon/publishable key is designed for browser use; protect tables with RLS.
    return jsonify({"supabase_url":os.getenv("SUPABASE_URL", "").rstrip("/"), "supabase_anon_key":os.getenv("SUPABASE_ANON_KEY", "")})

@app.post("/api/ai/explain")
def ai_explain():
    body=request.get_json(silent=True) or {}
    findings=body.get("findings", [])
    if not isinstance(findings,list): return jsonify({"error":"Invalid findings payload."}),400
    # Limit payload size and never send full source code or secrets to a model.
    compact={"source":str(body.get("source","Project"))[:180],"health":body.get("health"),"counts":body.get("counts",{}),"findings":findings[:18]}
    prompt=("You are RepoGuardian X, a cautious senior software reviewer. Explain these static-analysis findings in clear, practical language. "
            "Distinguish pattern matches from confirmed vulnerabilities. Prioritize up to five actions, include verification steps, do not claim you ran tests, "
            "and never request secrets. Respond in concise Markdown.\n\nSCAN SUMMARY:\n"+json.dumps(compact,ensure_ascii=False)[:14000])
    openrouter=os.getenv("OPENROUTER_API_KEY","").strip(); gemini=os.getenv("GEMINI_API_KEY","").strip()
    try:
        if openrouter:
            model=os.getenv("OPENROUTER_MODEL","openai/gpt-4o-mini")
            payload=json.dumps({"model":model,"messages":[{"role":"user","content":prompt}],"temperature":0.2,"max_tokens":1200}).encode()
            req=urllib.request.Request("https://openrouter.ai/api/v1/chat/completions",data=payload,headers={"Authorization":"Bearer "+openrouter,"Content-Type":"application/json","HTTP-Referer":request.host_url,"X-Title":"RepoGuardian X"},method="POST")
            with urllib.request.urlopen(req,timeout=25) as resp: result=json.loads(resp.read().decode())
            answer=result.get("choices",[{}])[0].get("message",{}).get("content","")
        elif gemini:
            model=os.getenv("GEMINI_MODEL","gemini-2.5-flash")
            url=f"https://generativelanguage.googleapis.com/v1beta/models/{urllib.parse.quote(model)}:generateContent?key={urllib.parse.quote(gemini)}"
            payload=json.dumps({"contents":[{"parts":[{"text":prompt}]}],"generationConfig":{"temperature":0.2,"maxOutputTokens":1200}}).encode()
            req=urllib.request.Request(url,data=payload,headers={"Content-Type":"application/json"},method="POST")
            with urllib.request.urlopen(req,timeout=25) as resp: result=json.loads(resp.read().decode())
            answer="".join(p.get("text","") for p in result.get("candidates",[{}])[0].get("content",{}).get("parts",[]))
        else:
            return jsonify({"error":"AI is not configured. Add OPENROUTER_API_KEY or GEMINI_API_KEY to your deployment environment."}),503
        if not answer: return jsonify({"error":"The AI provider returned an empty explanation."}),502
        return jsonify({"explanation":answer,"provider":"openrouter" if openrouter else "gemini"})
    except urllib.error.HTTPError as e:
        return jsonify({"error":f"AI provider request failed ({e.code}). Check the API key, model, and provider quota."}),502
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        app.logger.warning("AI explanation request failed: %s",type(e).__name__)
        return jsonify({"error":"AI provider is temporarily unavailable. Try again shortly."}),502

@app.post("/api/checkout")
def checkout():
    body=request.get_json(silent=True) or {}; plan=body.get("plan")
    price_env={"pro_monthly":"STRIPE_PRICE_PRO_MONTHLY","studio_monthly":"STRIPE_PRICE_STUDIO_MONTHLY"}.get(plan)
    if not price_env: return jsonify({"error":"Unknown subscription plan."}),400
    secret=os.getenv("STRIPE_SECRET_KEY","").strip(); price=os.getenv(price_env,"").strip()
    if not secret or not price:
        return jsonify({"error":"Subscription checkout is not configured yet. Set STRIPE_SECRET_KEY and the matching Stripe Price ID in deployment settings."}),503
    fields={"mode":"subscription","success_url":request.host_url.rstrip("/")+"/?checkout=success","cancel_url":request.host_url.rstrip("/")+"/#plans","line_items[0][price]":price,"line_items[0][quantity]":"1"}
    encoded=urllib.parse.urlencode(fields).encode()
    req=urllib.request.Request("https://api.stripe.com/v1/checkout/sessions",data=encoded,headers={"Authorization":"Bearer "+secret,"Content-Type":"application/x-www-form-urlencoded"},method="POST")
    try:
        with urllib.request.urlopen(req,timeout=20) as resp: result=json.loads(resp.read().decode())
        return jsonify({"url":result.get("url")})
    except urllib.error.HTTPError as e:
        app.logger.warning("Stripe checkout failed: %s",e.code)
        return jsonify({"error":"Stripe could not create checkout. Verify price IDs and account settings."}),502
    except urllib.error.URLError:
        return jsonify({"error":"Payment provider is temporarily unavailable."}),502

@app.get("/")
def home():
    return render_template("index.html")

@app.post("/api/analyze")
def analyze():
    mode=request.form.get("mode","upload")
    with tempfile.TemporaryDirectory(prefix="rgx_") as tmp:
        root=Path(tmp)/"project"; root.mkdir()
        label="Uploaded project"
        if mode=="repo":
            validated=validate_github_url(request.form.get("repo",""))
            if not validated: return jsonify({"error":"Enter a valid public GitHub HTTPS repository URL."}),400
            url,label=validated
            try:
                result=subprocess.run(["git","clone","--depth","1","--filter=blob:none",url,str(root)],capture_output=True,text=True,timeout=35,check=False)
            except FileNotFoundError:
                return jsonify({"error":"Git is not installed on this server. Install Git or use ZIP upload."}),400
            except subprocess.TimeoutExpired:
                return jsonify({"error":"Repository download timed out. Try a smaller public repository or upload a ZIP."}),408
            if result.returncode!=0:
                return jsonify({"error":"Could not fetch that public repository. Check the URL and repository visibility, or upload a ZIP instead."}),400
        else:
            upload=request.files.get("project")
            if not upload or not upload.filename: return jsonify({"error":"Choose a ZIP archive or source file first."}),400
            filename=Path(upload.filename).name
            if filename.lower().endswith(".zip"):
                archive=Path(tmp)/"upload.zip"; upload.save(archive)
                try:
                    with zipfile.ZipFile(archive) as zf:
                        members=zf.infolist()
                        if len(members)>MAX_FILES*3: return jsonify({"error":"ZIP contains too many entries."}),413
                        unpacked=sum(i.file_size for i in members)
                        if unpacked>MAX_UNPACKED: return jsonify({"error":"Uncompressed ZIP is too large (100 MB limit)."}),413
                        for info in members:
                            target=(root/info.filename).resolve()
                            if root.resolve() not in target.parents and target!=root.resolve():
                                return jsonify({"error":"ZIP contains an unsafe path; archive rejected."}),400
                        zf.extractall(root)
                except zipfile.BadZipFile: return jsonify({"error":"That file is not a valid ZIP archive."}),400
                label=filename
            else:
                ext=Path(filename).suffix.lower()
                if ext not in ALLOWED_SOURCE and filename.lower() not in {"dockerfile","makefile"}:
                    return jsonify({"error":"Unsupported file type. Upload a ZIP or a source/config file such as .py, .js, .ts, .java, .html, .css, .json, or .md."}),400
                dest=root/filename
                dest.write_bytes(upload.read(5*1024*1024+1))
                if dest.stat().st_size>5*1024*1024: return jsonify({"error":"Single-file upload limit is 5 MB."}),413
                label=filename
        data,status=analyze_tree(root,label)
        return jsonify(data),status

@app.errorhandler(413)
def too_large(_): return jsonify({"error":"Upload exceeds the 35 MB request limit."}),413

if __name__=="__main__":
    app.run(debug=False)
