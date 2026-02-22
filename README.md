
## Subject
CVE Request: Path Traversal via ZIP Upload in Joomla! 5.x Update Component

---

## Summary

A path traversal vulnerability exists in the Joomla! Update component (`com_joomlaupdate`) that allows authenticated Super Administrators to write arbitrary files outside the intended extraction directory during the update process. The vulnerability is located in the ZIP extraction handler at `administrator/components/com_joomlaupdate/extract.php`.

The `ZIPExtraction::readFileHeader()` method uses PHP's `basename()` function to validate file paths within uploaded ZIP archives. However, `basename()` only returns the filename component and does not prevent path traversal sequences, allowing an attacker to include entries like `../../../malicious.php` in a malicious update package.

---

## Technical Details

### Vulnerable Code Location
**File:** `administrator/components/com_joomlaupdate/extract.php`
**Line:** 1086
**Function:** `ZIPExtraction::readFileHeader()`

### Vulnerable Code Snippet
```php
// Line 1086-1089
if ((basename($this->fileHeader->file) == ".") || (basename($this->fileHeader->file) == "..")) {
    return false;
}
```

### Root Cause
The validation logic attempts to prevent directory traversal by checking if `basename()` equals `.` or `..`. However, this check is insufficient because:

1. `basename('../../../webshell.php')` returns `'webshell.php'` (not `.` or `..`)
2. The validation passes, allowing the traversal sequence
3. Later at line 1127, the file is written using the unsanitized path:
   ```php
   $this->fileHeader->file = $this->addPath . $this->fileHeader->file;
   // Results in: /var/www/html/../../../webshell.php
   ```

---

## Proof of Concept

### Prerequisites
- Valid Joomla Super Administrator credentials
- Access to `/administrator/` panel

### Exploitation Steps

1. **Create Malicious ZIP Package**
   - Include valid Joomla manifest: `administrator/manifests/files/joomla.xml`
   - Add malicious file with path traversal: `../../../webshell.php`

2. **Upload via Update Component**
   - Navigate to: `Components → Joomla! Update → Upload & Update`
   - Upload malicious ZIP package
   - Complete captive authentication (security re-auth)

3. **Trigger Extraction**
   - HTTP POST to `administrator/components/com_joomlaupdate/extract.php`
   - Parameters: `task=startExtract`, `password=<extraction_password>`
   - The password is obtained from the update installation page

4. **Result**
   - Arbitrary file written outside webroot
   - Remote code execution via uploaded webshell

### Exploit Code
A full working exploit is available demonstrating remote exploitation via HTTP.

**Usage:**
```bash
python3 exploit_joomla_final.py http://target.com admin password
```

---

## Impact

An authenticated attacker with Super Administrator privileges can:

1. **Arbitrary File Write:** Write files to any location writable by the web server user
2. **Remote Code Execution:** Upload PHP webshells for persistent access
3. **Privilege Escalation:** Potentially escalate from web application access to system-level access
4. **Data Exfiltration:** Access sensitive files outside the web directory
5. **System Compromise:** Full compromise of the web server

**Attack Scenario:**
1. Attacker compromises Super Admin account (phishing, credential stuffing, etc.)
2. Uploads malicious "update" package via legitimate Joomla interface
3. Gains webshell access and establishes persistence
4. Pivots to internal network or exfiltrates data

---

## Affected Components

- `administrator/components/com_joomlaupdate/extract.php` (ZIPExtraction class)
- `administrator/components/com_joomlaupdate/src/Controller/UpdateController.php`
- `administrator/components/com_joomlaupdate/src/Model/UpdateModel.php`

---

## Remediation Recommendations

### Immediate Fix
Replace the insufficient `basename()` check with proper path validation:

```php
// Secure implementation
private function readFileHeader(): bool
{
    // ... existing code ...

    // Sanitize and validate file path
    $file = $this->fileHeader->file;

    // Remove any directory traversal sequences
    $file = str_replace(['../', '..\\'], '', $file);

    // Ensure the file is within the extraction directory
    $realPath = realpath($this->addPath . '/' . $file);
    $basePath = realpath($this->addPath);

    if ($realPath === false || strpos($realPath, $basePath) !== 0) {
        $this->setError('Invalid file path detected');
        return false;
    }

    $this->fileHeader->file = $file;

    // ... rest of code ...
}
```

---

## Credits

**Researcher:** Pedro Henrique de Almeida Silva
**Contact:** contato@vanalyze.io
---

## References

- Joomla! CMS: https://www.joomla.org/
- CWE-22: https://cwe.mitre.org/data/definitions/22.html
- OWASP Path Traversal: https://owasp.org/www-community/attacks/Path_Traversal
- Vulnerable Code: `administrator/components/com_joomlaupdate/extract.php:1086`
---

## Additional Notes

- This vulnerability requires Super Administrator access, but represents a significant security risk as it allows privilege escalation beyond the web application boundary
- The vulnerability affects the core update mechanism, which is a critical security component
- Exploitation is trivial once Super Admin access is obtained
- The vulnerability may affect older Joomla versions (3.x, 4.x) and should be investigated

