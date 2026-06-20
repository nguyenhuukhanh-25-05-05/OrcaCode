"""Tests for security scanner."""

from core.reviewer.security import SecurityScanner


def test_detect_api_key():
    scanner = SecurityScanner()
    issues = scanner.scan_file("config.py", 'API_KEY = "sk-1234567890abcdef1234567890abcdef"')
    assert len(issues) >= 1
    assert any("API key" in i.message or "secret" in i.message.lower() for i in issues)


def test_detect_aws_key():
    scanner = SecurityScanner()
    issues = scanner.scan_file("test.py", 'key = "AKIA1234567890ABCDEF"')
    aws = [i for i in issues if "AWS" in i.message]
    assert len(aws) >= 1


def test_detect_private_key():
    scanner = SecurityScanner()
    issues = scanner.scan_file("key.pem", "-----BEGIN RSA PRIVATE KEY-----\nAAAA")
    assert len(issues) >= 1


def test_detect_sql_injection_fstring():
    scanner = SecurityScanner()
    issues = scanner.scan_file("db.py", 'cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")')
    sql = [i for i in issues if "SQL" in i.message or "injection" in i.message.lower()]
    assert len(sql) >= 1


def test_detect_shell_true():
    scanner = SecurityScanner()
    issues = scanner.scan_file("run.py", 'subprocess.run("ls -la", shell=True)')
    assert any("shell=True" in i.message for i in issues)


def test_detect_os_system():
    scanner = SecurityScanner()
    issues = scanner.scan_file("run.py", 'os.system("rm -rf /")')
    assert any("os.system" in i.message for i in issues)


def test_detect_inner_html():
    scanner = SecurityScanner()
    issues = scanner.scan_file("app.js", 'element.innerHTML = userInput;')
    assert any("innerHTML" in i.message for i in issues)


def test_detect_dangerously_set_inner_html():
    scanner = SecurityScanner()
    issues = scanner.scan_file("App.tsx", 'dangerouslySetInnerHTML={{ __html: content }}')
    assert any("dangerouslySetInnerHTML" in i.message for i in issues)


def test_detect_eval():
    scanner = SecurityScanner()
    issues = scanner.scan_file("test.py", 'result = eval(user_input)')
    assert any("eval" in i.message.lower() for i in issues)


def test_detect_pickle():
    scanner = SecurityScanner()
    issues = scanner.scan_file("data.py", 'data = pickle.loads(raw)')
    assert any("pickle" in i.message.lower() for i in issues)


def test_detect_yaml_load():
    scanner = SecurityScanner()
    issues = scanner.scan_file("config.py", 'cfg = yaml.load(content)')
    assert any("yaml.load" in i.message.lower() or "yaml" in i.message.lower() for i in issues)


def test_detect_requests_verify_false():
    scanner = SecurityScanner()
    issues = scanner.scan_file("http.py", 'requests.get("https://example.com", verify=False)')
    assert any("SSL" in i.message or "TLS" in i.message for i in issues)


def test_scan_clean_file():
    scanner = SecurityScanner()
    issues = scanner.scan_file("clean.py", "def add(a, b):\n    return a + b\n")
    assert len(issues) == 0


def test_scan_files_dict():
    scanner = SecurityScanner()
    files = {
        "good.py": "x = 1\n",
        "bad.py": 'key = "AKIA1234567890ABCDEF"\n',
    }
    result = scanner.scan_files(files)
    assert result.count >= 1
    assert not result.passed


def test_issue_has_location():
    scanner = SecurityScanner()
    issues = scanner.scan_file("test.py", 'API_KEY = "sk-1234567890abcdef1234567890abcdef"\n')
    assert len(issues) >= 1
    assert issues[0].line > 0
    assert issues[0].file == "test.py"


def test_scan_empty_file():
    scanner = SecurityScanner()
    issues = scanner.scan_file("empty.py", "")
    assert len(issues) == 0
