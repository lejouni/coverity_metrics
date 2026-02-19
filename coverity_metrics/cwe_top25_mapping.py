"""
CWE Top 25 Most Dangerous Software Weaknesses (2025)

Based on CWE Top 25 2025 specification from MITRE
https://cwe.mitre.org/top25/archive/2025/2025_cwe_top25.html
"""

CWE_TOP_25_2025 = {
    1: {
        "cwe_id": 79,
        "name": "Improper Neutralization of Input During Web Page Generation ('Cross-site Scripting')",
        "score": 63.72,
        "rank": 1
    },
    2: {
        "cwe_id": 89,
        "name": "Improper Neutralization of Special Elements used in an SQL Command ('SQL Injection')",
        "score": 59.93,
        "rank": 2
    },
    3: {
        "cwe_id": 78,
        "name": "Improper Neutralization of Special Elements used in an OS Command ('OS Command Injection')",
        "score": 47.46,
        "rank": 3
    },
    4: {
        "cwe_id": 352,
        "name": "Cross-Site Request Forgery (CSRF)",
        "score": 44.16,
        "rank": 4
    },
    5: {
        "cwe_id": 434,
        "name": "Unrestricted Upload of File with Dangerous Type",
        "score": 42.47,
        "rank": 5
    },
    6: {
        "cwe_id": 22,
        "name": "Improper Limitation of a Pathname to a Restricted Directory ('Path Traversal')",
        "score": 40.35,
        "rank": 6
    },
    7: {
        "cwe_id": 77,
        "name": "Improper Neutralization of Special Elements used in a Command ('Command Injection')",
        "score": 37.48,
        "rank": 7
    },
    8: {
        "cwe_id": 306,
        "name": "Missing Authentication for Critical Function",
        "score": 36.52,
        "rank": 8
    },
    9: {
        "cwe_id": 20,
        "name": "Improper Input Validation",
        "score": 35.43,
        "rank": 9
    },
    10: {
        "cwe_id": 862,
        "name": "Missing Authorization",
        "score": 34.39,
        "rank": 10
    },
    11: {
        "cwe_id": 287,
        "name": "Improper Authentication",
        "score": 33.90,
        "rank": 11
    },
    12: {
        "cwe_id": 269,
        "name": "Improper Privilege Management",
        "score": 33.38,
        "rank": 12
    },
    13: {
        "cwe_id": 798,
        "name": "Use of Hard-coded Credentials",
        "score": 33.12,
        "rank": 13
    },
    14: {
        "cwe_id": 502,
        "name": "Deserialization of Untrusted Data",
        "score": 31.84,
        "rank": 14
    },
    15: {
        "cwe_id": 918,
        "name": "Server-Side Request Forgery (SSRF)",
        "score": 30.65,
        "rank": 15
    },
    16: {
        "cwe_id": 119,
        "name": "Improper Restriction of Operations within the Bounds of a Memory Buffer",
        "score": 29.75,
        "rank": 16
    },
    17: {
        "cwe_id": 476,
        "name": "NULL Pointer Dereference",
        "score": 29.39,
        "rank": 17
    },
    18: {
        "cwe_id": 416,
        "name": "Use After Free",
        "score": 28.82,
        "rank": 18
    },
    19: {
        "cwe_id": 120,
        "name": "Buffer Copy without Checking Size of Input ('Classic Buffer Overflow')",
        "score": 28.60,
        "rank": 19
    },
    20: {
        "cwe_id": 125,
        "name": "Out-of-bounds Read",
        "score": 28.08,
        "rank": 20
    },
    21: {
        "cwe_id": 787,
        "name": "Out-of-bounds Write",
        "score": 27.97,
        "rank": 21
    },
    22: {
        "cwe_id": 190,
        "name": "Integer Overflow or Wraparound",
        "score": 27.69,
        "rank": 22
    },
    23: {
        "cwe_id": 327,
        "name": "Use of a Broken or Risky Cryptographic Algorithm",
        "score": 26.09,
        "rank": 23
    },
    24: {
        "cwe_id": 362,
        "name": "Concurrent Execution using Shared Resource with Improper Synchronization ('Race Condition')",
        "score": 25.83,
        "rank": 24
    },
    25: {
        "cwe_id": 863,
        "name": "Incorrect Authorization",
        "score": 25.44,
        "rank": 25
    }
}


def get_cwe_top25_info(cwe_id):
    """
    Get CWE Top 25 ranking information for a CWE ID
    
    Args:
        cwe_id: Integer CWE ID
        
    Returns:
        Dict with rank, name, score or None if not in Top 25
    """
    for rank, data in CWE_TOP_25_2025.items():
        if data['cwe_id'] == cwe_id:
            return {
                'rank': rank,
                'cwe_id': cwe_id,
                'name': data['name'],
                'score': data['score']
            }
    return None


def get_all_cwe_top25():
    """
    Get all CWE Top 25 entries
    
    Returns:
        List of dicts with full CWE Top 25 information
    """
    return [
        {
            'rank': rank,
            'cwe_id': data['cwe_id'],
            'name': data['name'],
            'score': data['score']
        }
        for rank, data in sorted(CWE_TOP_25_2025.items())
    ]


def is_in_cwe_top25(cwe_id):
    """
    Check if a CWE ID is in the Top 25
    
    Args:
        cwe_id: Integer CWE ID
        
    Returns:
        Boolean
    """
    return any(data['cwe_id'] == cwe_id for data in CWE_TOP_25_2025.values())
