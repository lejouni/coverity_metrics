"""
OWASP Top 10 2025 to CWE Mapping

Based on OWASP Top 10 2025 specification
"""

OWASP_TOP_10_2025 = {
    "A01:2025-Broken Access Control": {
        "description": "Restrictions on what authenticated users are allowed to do are often not properly enforced",
        "cwe_ids": [
            22,   # Path Traversal
            23,   # Relative Path Traversal  
            35,   # Path Traversal: '.../...//'
            59,   # Improper Link Resolution Before File Access
            200,  # Exposure of Sensitive Information
            201,  # Information Exposure Through Sent Data
            219,  # Sensitive Data Under Web Root
            264,  # Permissions, Privileges, and Access Controls
            275,  # Permission Issues
            276,  # Incorrect Default Permissions
            284,  # Improper Access Control
            285,  # Improper Authorization
            352,  # Cross-Site Request Forgery (CSRF)
            377,  # Insecure Temporary File
            402,  # Transmission of Private Resources
            425,  # Direct Request ('Forced Browsing')
            441,  # Unintended Proxy or Intermediary
            497,  # Exposure of System Data to an Unauthorized Control Sphere
            538,  # File and Directory Information Exposure
            540,  # Inclusion of Sensitive Information in Source Code
            548,  # Information Exposure Through Directory Listing
            551,  # Incorrect Privilege Assignment
            552,  # Files or Directories Accessible to External Parties
            566,  # Authorization Bypass Through SQL Injection
            601,  # URL Redirection to Untrusted Site
            639,  # Authorization Bypass Through User-Controlled Key
            651,  # Exposure of WSDL File
            668,  # Exposure of Resource to Wrong Sphere
            706,  # Use of Incorrectly-Resolved Name or Reference
            732,  # Incorrect Permission Assignment for Critical Resource
            766,  # Critical Variable Declared Public
            767,  # Access to Critical Private Variable via Public Method
            770,  # Allocation of Resources Without Limits or Throttling
            772,  # Missing Release of Resource after Effective Lifetime
            777,  # Regular Expression without Anchors
            862,  # Missing Authorization
            863,  # Incorrect Authorization
            913,  # Improper Control of Dynamically-Managed Code Resources
            922,  # Insecure Storage of Sensitive Information
            1275, # Sensitive Cookie with Improper SameSite Attribute
        ]
    },
    "A02:2025-Cryptographic Failures": {
        "description": "Failures related to cryptography which often lead to exposure of sensitive data",
        "cwe_ids": [
            5,    # J2EE Misconfiguration: Data Transmission Without Encryption
            209,  # Generation of Error Message Containing Sensitive Information
            256,  # Unprotected Storage of Credentials
            257,  # Storing Passwords in a Recoverable Format
            258,  # Empty Password in Configuration File
            259,  # Use of Hard-coded Password
            260,  # Password in Configuration File
            261,  # Weak Encoding for Password
            262,  # Not Using Password Aging
            263,  # Password Aging with Long Expiration
            266,  # Incorrect Privilege Assignment
            284,  # Improper Access Control
            285,  # Improper Authorization
            286,  # Incorrect User Management
            287,  # Improper Authentication
            289,  # Authentication Bypass by Alternate Name
            290,  # Authentication Bypass by Spoofing
            291,  # Reliance on IP Address for Authentication
            292,  # Trusting Self-reported DNS Name
            293,  # Using Referer Field for Authentication
            294,  # Authentication Bypass by Capture-replay
            295,  # Improper Certificate Validation
            296,  # Improper Following of Chain of Trust
            297,  # Improper Validation of Certificate with Host Mismatch
            298,  # Improper Validation of Certificate Expiration
            299,  # Improper Check for Certificate Revocation
            300,  # Channel Accessible by Non-Endpoint
            301,  # Reflection Attack in an Authentication Protocol
            302,  # Authentication Bypass by Assumed-Immutable Data
            303,  # Incorrect Implementation of Authentication Algorithm
            304,  # Missing Critical Step in Authentication
            305,  # Authentication Bypass by Primary Weakness
            306,  # Missing Authentication for Critical Function
            307,  # Improper Restriction of Excessive Authentication Attempts
            308,  # Use of Single-factor Authentication
            309,  # Use of Password System for Primary Authentication
            310,  # Cryptographic Issues
            311,  # Missing Encryption of Sensitive Data
            312,  # Cleartext Storage of Sensitive Information
            313,  # Cleartext Storage in a File or on Disk
            314,  # Cleartext Storage in the Registry
            315,  # Cleartext Storage of Sensitive Information in a Cookie
            316,  # Cleartext Storage of Sensitive Information in Memory
            317,  # Cleartext Storage of Sensitive Information in GUI
            318,  # Cleartext Storage of Sensitive Information in Executable
            319,  # Cleartext Transmission of Sensitive Information
            320,  # Key Management Errors
            321,  # Use of Hard-coded Cryptographic Key
            322,  # Key Exchange without Entity Authentication
            323,  # Reusing a Nonce, Key Pair in Encryption
            324,  # Use of a Key Past its Expiration Date
            325,  # Missing Required Cryptographic Step
            326,  # Inadequate Encryption Strength
            327,  # Use of a Broken or Risky Cryptographic Algorithm
            328,  # Reversible One-Way Hash
            329,  # Not Using a Random IV with CBC Mode
            330,  # Use of Insufficiently Random Values
            331,  # Insufficient Entropy
            332,  # Insufficient Entropy in PRNG
            333,  # Improper Handling of Insufficient Entropy in TRNG
            334,  # Small Space Used in Random Number Generator
            335,  # Incorrect Usage of Seeds in Pseudo-Random Number Generator
            336,  # Same Seed in Multiple PRNG Instances
            337,  # Predictable Seed in PRNG
            338,  # Use of Cryptographically Weak PRNG
            340,  # Generation of Predictable Numbers or Identifiers
            347,  # Improper Verification of Cryptographic Signature
            523,  # Unprotected Transport of Credentials
            720,  # OWASP Top Ten 2007 Category A9 - Insecure Communications
            757,  # Selection of Less-Secure Algorithm During Negotiation
            759,  # Use of a One-Way Hash without a Salt
            760,  # Use of a One-Way Hash with a Predictable Salt
            780,  # Use of RSA Algorithm without OAEP
            798,  # Use of Hard-coded Credentials
            916,  # Use of Password Hash With Insufficient Computational Effort
            1204, # Generation of Weak Initialization Vector (IV)
            1240, # Use of a Risky Cryptographic Primitive
            1241, # Use of Predictable Algorithm in Random Number Generator
            1310, # Missing Ability to Patch ROM Code
            1311, # Improper Translation of Security Attributes by Fabric Bridge
        ]
    },
    "A03:2025-Injection": {
        "description": "An application is vulnerable to injection attacks when user-supplied data is not validated, filtered, or sanitized",
        "cwe_ids": [
            20,   # Improper Input Validation
            73,   # External Control of File Name or Path
            74,   # Improper Neutralization of Special Elements in Output
            75,   # Failure to Sanitize Special Elements into a Different Plane
            76,   # Improper Neutralization of Equivalent Special Elements
            77,   # Command Injection
            78,   # OS Command Injection
            79,   # Cross-site Scripting (XSS)
            80,   # Improper Neutralization of Script-Related HTML Tags
            83,   # Improper Neutralization of Script in Attributes
            87,   # Improper Neutralization of Alternate XSS Syntax
            88,   # Argument Injection
            89,   # SQL Injection
            90,   # LDAP Injection
            91,   # XML Injection
            93,   # Improper Neutralization of CRLF Sequences
            94,   # Improper Control of Generation of Code
            95,   # Improper Neutralization of Directives in Dynamically Evaluated Code
            96,   # Improper Neutralization of Directives in Statically Saved Code
            97,   # Improper Neutralization of Server-Side Includes (SSI)
            98,   # Improper Control of Filename for Include/Require Statement in PHP Program
            99,   # Improper Control of Resource Identifiers
            100,  # Deprecated: Was catch-all for input validation issues
            113,  # Improper Neutralization of CRLF Sequences in HTTP Headers
            116,  # Improper Encoding or Escaping of Output
            117,  # Improper Output Neutralization for Logs
            138,  # Improper Neutralization of Special Elements
            184,  # Incomplete List of Disallowed Inputs
            470,  # Use of Externally-Controlled Input to Select Classes or Code
            471,  # Modification of Assumed-Immutable Data
            564,  # SQL Injection: Hibernate
            610,  # Externally Controlled Reference to a Resource
            643,  # Improper Neutralization of Data within XPath Expressions
            652,  # Improper Neutralization of Data within XQuery Expressions
            917,  # Improper Neutralization of Special Elements used in an Expression Language Statement
            1236, # Improper Neutralization of Formula Elements in a CSV File
        ]
    },
    "A04:2025-Insecure Design": {
        "description": "Missing or ineffective control design; focuses on risks related to design and architectural flaws",
        "cwe_ids": [
            73,   # External Control of File Name or Path
            183,  # Permissive List of Allowed Inputs
            209,  # Generation of Error Message Containing Sensitive Information
            213,  # Exposure of Sensitive Information Due to Incompatible Policies
            235,  # Improper Handling of Extra Parameters
            256,  # Unprotected Storage of Credentials
            257,  # Storing Passwords in a Recoverable Format
            266,  # Incorrect Privilege Assignment
            269,  # Improper Privilege Management
            279,  # Incorrect Execution-Assigned Permissions
            280,  # Improper Handling of Insufficient Permissions or Privileges
            311,  # Missing Encryption of Sensitive Data
            312,  # Cleartext Storage of Sensitive Information
            313,  # Cleartext Storage in a File or on Disk
            316,  # Cleartext Storage of Sensitive Information in Memory
            419,  # Unprotected Primary Channel
            430,  # Deployment of Wrong Handler
            434,  # Unrestricted Upload of File with Dangerous Type
            444,  # Inconsistent Interpretation of HTTP Requests
            451,  # User Interface (UI) Misrepresentation of Critical Information
            472,  # External Control of Assumed-Immutable Web Parameter
            501,  # Trust Boundary Violation
            522,  # Insufficiently Protected Credentials
            525,  # Use of Web Browser Cache Containing Sensitive Information
            539,  # Use of Persistent Cookies Containing Sensitive Information
            579,  # J2EE Bad Practices: Non-serializable Object Stored in Session
            598,  # Use of GET Request Method With Sensitive Query Strings
            602,  # Client-Side Enforcement of Server-Side Security
            641,  # Improper Restriction of Names for Files and Other Resources
            653,  # Insufficient Compartmentalization
            656,  # Reliance on Security Through Obscurity
            657,  # Violation of Secure Design Principles
            799,  # Improper Control of Interaction Frequency
            807,  # Reliance on Untrusted Inputs in a Security Decision
            840,  # Business Logic Errors
            841,  # Improper Enforcement of Behavioral Workflow
            842,  # Placement of User into Incorrect Group
            843,  # Access of Resource Using Incompatible Type
            859,  # Modification of Assumed-Immutable Data
            920,  # Improper Restriction of Power Consumption
            1021, # Improper Restriction of Rendered UI Layers or Frames
            1173, # Improper Use of Validation Framework
            1209, # Failure to Disable Reserved Bits
            1220, # Insufficient Granularity of Access Control
            1254, # Incorrect Comparison Logic Granularity
            1263, # Improper Physical Access Control
            1270, # Generation of Incorrect Security Identifiers
            1283, # Mutable Attestation or Measurement Reporting Data
            1287, # Improper Validation of Specified Type of Input
            1288, # Improper Validation of Consistency within Input
            1297, # Unprotected Confidential Information on Device is Accessible by OSAT
        ]
    },
    "A05:2025-Security Misconfiguration": {
        "description": "Missing appropriate security hardening or improperly configured permissions",
        "cwe_ids": [
            2,    # Environment
            11,   # ASP.NET Misconfiguration
            13,   # ASP.NET Misconfiguration: Password in Configuration File
            15,   # External Control of System or Configuration Setting
            16,   # Configuration
            260,  # Password in Configuration File
            315,  # Cleartext Storage of Sensitive Information in a Cookie
            520,  # .NET Misconfiguration: Use of Impersonation
            526,  # Exposure of Sensitive Information Through Environmental Variables
            537,  # Java Runtime Error Message Containing Sensitive Information
            541,  # Inclusion of Sensitive Information in an Include File
            614,  # Sensitive Cookie in HTTPS Session Without 'Secure' Attribute
            756,  # Missing Custom Error Page
            776,  # Improper Restriction of Recursive Entity References in DTDs
            942,  # Permissive Cross-domain Policy with Untrusted Domains
            1004, # Sensitive Cookie Without 'HttpOnly' Flag
            1032, # OWASP Top Ten 2017 Category A6 - Security Misconfiguration
            1174, # ASP.NET Misconfiguration: Improper Model Validation
        ]
    },
    "A06:2025-Vulnerable and Outdated Components": {
        "description": "Using components with known vulnerabilities or that are out of date or unsupported",
        "cwe_ids": [
            1035, # 2011 Top 25 - Insecure Interaction Between Components
            1104, # Use of Unmaintained Third Party Components
        ]
    },
    "A07:2025-Identification and Authentication Failures": {
        "description": "Confirmation of the user's identity, authentication, and session management is critical to protect against authentication-related attacks",
        "cwe_ids": [
            255,  # Credentials Management
            259,  # Use of Hard-coded Password
            287,  # Improper Authentication
            288,  # Authentication Bypass Using an Alternate Path or Channel
            289,  # Authentication Bypass by Alternate Name
            290,  # Authentication Bypass by Spoofing
            294,  # Authentication Bypass by Capture-replay
            295,  # Improper Certificate Validation
            297,  # Improper Validation of Certificate with Host Mismatch
            300,  # Channel Accessible by Non-Endpoint
            302,  # Authentication Bypass by Assumed-Immutable Data
            303,  # Incorrect Implementation of Authentication Algorithm
            304,  # Missing Critical Step in Authentication
            306,  # Missing Authentication for Critical Function
            307,  # Improper Restriction of Excessive Authentication Attempts
            346,  # Origin Validation Error
            384,  # Session Fixation
            521,  # Weak Password Requirements
            522,  # Insufficiently Protected Credentials
            613,  # Insufficient Session Expiration
            620,  # Unverified Password Change
            640,  # Weak Password Recovery Mechanism for Forgotten Password
            798,  # Use of Hard-coded Credentials
            940,  # Improper Verification of Source of a Communication Channel
            1216, # Lockout Mechanism Errors
        ]
    },
    "A08:2025-Software and Data Integrity Failures": {
        "description": "Code and infrastructure that does not protect against integrity violations",
        "cwe_ids": [
            345,  # Insufficient Verification of Data Authenticity
            353,  # Missing Support for Integrity Check
            426,  # Untrusted Search Path
            494,  # Download of Code Without Integrity Check
            502,  # Deserialization of Untrusted Data
            565,  # Reliance on Cookies without Validation and Integrity Checking
            784,  # Reliance on Cookies without Validation and Integrity Checking in a Security Decision
            829,  # Inclusion of Functionality from Untrusted Control Sphere
            830,  # Inclusion of Web Functionality from an Untrusted Source
            915,  # Improperly Controlled Modification of Dynamically-Determined Object Attributes
        ]
    },
    "A09:2025-Security Logging and Monitoring Failures": {
        "description": "Insufficient logging and monitoring, coupled with missing or ineffective integration with incident response",
        "cwe_ids": [
            117,  # Improper Output Neutralization for Logs
            223,  # Omission of Security-relevant Information
            532,  # Insertion of Sensitive Information into Log File
            533,  # DEPRECATED: Information Exposure Through Server Log Files
            778,  # Insufficient Logging
            779,  # Logging of Excessive Data
            780,  # Use of RSA Algorithm without OAEP
            787,  # Out-of-bounds Write
            918,  # Server-Side Request Forgery (SSRF)
            1188, # Insecure Default Initialization of Resource
        ]
    },
    "A10:2025-Server-Side Request Forgery (SSRF)": {
        "description": "SSRF flaws occur when a web application fetches a remote resource without validating the user-supplied URL",
        "cwe_ids": [
            918,  # Server-Side Request Forgery (SSRF)
        ]
    }
}


def get_owasp_category_for_cwe(cwe_id):
    """
    Map a CWE ID to its primary OWASP Top 10 2025 category
    
    Args:
        cwe_id: Integer CWE ID
        
    Returns:
        Tuple of (category_id, category_name, description) or None if not mapped
    """
    for category_id, data in OWASP_TOP_10_2025.items():
        if cwe_id in data['cwe_ids']:
            return (category_id, category_id, data['description'])
    return None


def get_all_owasp_categories():
    """
    Get all OWASP Top 10 2025 categories with their descriptions
    
    Returns:
        List of tuples: (category_id, category_name, description, cwe_count)
    """
    return [
        (cat_id, cat_id, data['description'], len(data['cwe_ids']))
        for cat_id, data in OWASP_TOP_10_2025.items()
    ]
