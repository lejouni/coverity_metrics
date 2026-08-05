"""
OWASP Top 10 2025 to CWE Mapping

Authoritative source: https://owasp.org/Top10/2025/
CWE lists below are copied verbatim from each category's
"List of Mapped CWEs" section on owasp.org (verified against the
per-category Score table "CWEs Mapped" count).

Each entry also carries `score_data` — the Avg Weighted Exploit and
Avg Weighted Impact values (0-10, CVSS-derived) from the category's
Score table on owasp.org. Consumers combine these with per-project
defect counts to compute a risk-adjusted priority score.

Category ordering follows the official 2025 ranking:
    A01 Broken Access Control
    A02 Security Misconfiguration
    A03 Software Supply Chain Failures        (NEW/renamed from 2021 A06)
    A04 Cryptographic Failures
    A05 Injection
    A06 Insecure Design
    A07 Authentication Failures                (renamed from 2021 A07)
    A08 Software or Data Integrity Failures    (slight name change)
    A09 Security Logging & Alerting Failures   (slight name change)
    A10 Mishandling of Exceptional Conditions  (NEW - replaces 2021 A10 SSRF;
                                                SSRF is now folded into A01)
"""

OWASP_TOP_10_2025 = {
    "A01:2025-Broken Access Control": {
        "description": "Restrictions on what authenticated users are allowed to do are often not properly enforced. SSRF (CWE-918) is now included in this category.",
        "cwe_ids": [
            22, 23, 36, 59, 61, 65,
            200, 201, 219, 276, 281, 282, 283, 284, 285,
            352, 359, 377, 379, 402, 424, 425, 441, 497,
            538, 540, 548, 552, 566, 601, 615, 639, 668,
            732, 749, 862, 863, 918, 922, 1275,
        ],
        "score_data": {"exploit_score": 7.04, "impact_score": 3.84},
    },
    "A02:2025-Security Misconfiguration": {
        "description": "Missing or insecure default configurations, incomplete setups, and unhardened services expose applications to attack.",
        "cwe_ids": [
            5, 11, 13, 15, 16,
            260, 315, 489, 526, 547, 611, 614, 776, 942,
            1004, 1174,
        ],
        "score_data": {"exploit_score": 7.96, "impact_score": 3.97},
    },
    "A03:2025-Software Supply Chain Failures": {
        "description": "Risks arising from third-party components, dependencies, and build/distribution pipelines whose integrity or provenance cannot be verified. Broadens 2021 A06 (Vulnerable and Outdated Components).",
        "cwe_ids": [
            447, 1035, 1104, 1329, 1357, 1395,
        ],
        "score_data": {"exploit_score": 8.17, "impact_score": 5.23},
    },
    "A04:2025-Cryptographic Failures": {
        "description": "Failures related to cryptography (or lack thereof) that often lead to exposure of sensitive data.",
        "cwe_ids": [
            261, 296,
            319, 320, 321, 322, 323, 324, 325, 326, 327, 328, 329,
            330, 331, 332, 334, 335, 336, 337, 338, 340, 342, 347,
            523, 757, 759, 760, 780, 916,
            1240, 1241,
        ],
        "score_data": {"exploit_score": 7.23, "impact_score": 3.90},
    },
    "A05:2025-Injection": {
        "description": "User-supplied data is not validated, filtered, or sanitized by the application, enabling execution of unintended commands or unauthorized access to data.",
        "cwe_ids": [
            20, 74, 76, 77, 78, 79, 80, 83, 86, 88, 89,
            90, 91, 93, 94, 95, 96, 97, 98, 99,
            103, 104, 112, 113, 114, 115, 116, 129, 159,
            470, 493, 500, 564, 610, 643, 644, 917,
        ],
        "score_data": {"exploit_score": 7.15, "impact_score": 4.32},
    },
    "A06:2025-Insecure Design": {
        "description": "Risks related to design and architectural flaws — missing or ineffective control design that cannot be fixed by a perfect implementation alone.",
        "cwe_ids": [
            73, 183, 256, 266, 269, 286,
            311, 312, 313, 316, 362, 382,
            419, 434, 436, 444, 451, 454, 472,
            501, 522, 525, 539, 598,
            602, 628, 642, 646, 653, 656, 657, 676, 693,
            799, 807, 841,
            1021, 1022, 1125,
        ],
        "score_data": {"exploit_score": 6.96, "impact_score": 4.05},
    },
    "A07:2025-Authentication Failures": {
        "description": "Weaknesses that let attackers impersonate users — credential stuffing, weak/default credentials, broken session management, missing or ineffective MFA.",
        "cwe_ids": [
            258, 259, 287, 288, 289, 290, 291, 293, 294, 295,
            297, 298, 299, 300, 302, 303, 304, 305, 306, 307,
            308, 309, 346, 350, 384,
            521, 613, 620, 640, 798,
            940, 941,
            1390, 1391, 1392, 1393,
        ],
        "score_data": {"exploit_score": 7.69, "impact_score": 4.44},
    },
    "A08:2025-Software or Data Integrity Failures": {
        "description": "Code and infrastructure that do not protect against invalid or untrusted code or data being treated as trusted — includes insecure deserialization and unverified auto-updates.",
        "cwe_ids": [
            345, 353, 426, 427, 494, 502, 506, 509,
            565, 784, 829, 830, 915, 926,
        ],
        "score_data": {"exploit_score": 7.11, "impact_score": 4.79},
    },
    "A09:2025-Security Logging and Alerting Failures": {
        "description": "Insufficient logging, monitoring, detection, and alerting means attacks and breaches go undetected and unaddressed.",
        "cwe_ids": [
            117, 221, 223, 532, 778,
        ],
        "score_data": {"exploit_score": 7.19, "impact_score": 2.65},
    },
    "A10:2025-Mishandling of Exceptional Conditions": {
        "description": "Applications fail to properly detect, handle, or recover from exceptional conditions (errors, exceptions, resource-exhaustion, unexpected state) — leading to crashes, information leaks, or bypass of security logic.",
        "cwe_ids": [
            209, 215, 234, 235, 248, 252, 274, 280,
            369, 390, 391, 394, 396, 397,
            460, 476, 478, 484,
            550, 636, 703, 754, 755, 756,
        ],
        "score_data": {"exploit_score": 7.11, "impact_score": 3.81},
    },
}


def get_owasp_category_for_cwe(cwe_id):
    """
    Map a CWE ID to its primary OWASP Top 10 2025 category.

    Args:
        cwe_id: Integer CWE ID

    Returns:
        Tuple of (category_id, category_name, description) or None if not mapped.
        (category_id and category_name are identical strings, e.g.
        "A10:2025-Mishandling of Exceptional Conditions" — the pair is kept
        for backward compatibility with callers that unpack three values.)
    """
    for category_id, data in OWASP_TOP_10_2025.items():
        if cwe_id in data['cwe_ids']:
            return (category_id, category_id, data['description'])
    return None


def get_all_owasp_categories():
    """
    Get all OWASP Top 10 2025 categories with their descriptions.

    Returns:
        List of tuples: (category_id, category_name, description, cwe_count)
    """
    return [
        (cat_id, cat_id, data['description'], len(data['cwe_ids']))
        for cat_id, data in OWASP_TOP_10_2025.items()
    ]
