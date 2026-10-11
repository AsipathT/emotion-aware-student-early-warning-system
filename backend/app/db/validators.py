"""
backend/app/db/validators.py

Feature 25: Pydantic to MongoDB $jsonSchema Validator Generator.
Transforms Pydantic v2 storage models into strict, self-contained MongoDB
$jsonSchema validation specifications.

════════════════════════════════════════════════════════════════════════════════
LIMITATIONS & APPLICATION-LAYER RULES
════════════════════════════════════════════════════════════════════════════════
MongoDB $jsonSchema validation operates on individual document field assertions.
Certain scientific and business contract invariants CANNOT be expressed in
MongoDB's standard $jsonSchema specification and remain strictly enforced at the
FastAPI application layer:

1. Cross-Field Arithmetic Constraints:
   - RiskAssessment: Modality contributions (affective + behavioral + academic)
     must sum to 1.0 within tolerance 0.01. $jsonSchema cannot perform mathematical
     additions across sibling properties.
2. Inter-Element Sequential Invariants:
   - InterventionRecommendation: Candidate ranks must be unique, consecutive integers
     starting from 1 to N (1..N). $jsonSchema cannot evaluate consecutive relationships
     across arbitrary array items.
3. Complex Natural Language Scans:
   - Deep NLP PII scrubbing (spaCy PERSON entity extraction) is performed prior to
     storage in the application layer. Database schema enforces regex safety net patterns.
"""

import copy
from typing import Any, Dict, List, Type
from pydantic import BaseModel

from app.db import collections as col
from app.db import storage_models as sm


def _resolve_refs(schema_node: Any, defs: Dict[str, Any]) -> Any:
    """Recursively inlines all $ref definitions using the provided $defs map."""
    if isinstance(schema_node, dict):
        if "$ref" in schema_node:
            ref_path = schema_node["$ref"]
            # Typically '#/$defs/ModelName'
            ref_name = ref_path.split("/")[-1]
            if ref_name in defs:
                resolved = copy.deepcopy(defs[ref_name])
                # Recursively resolve any nested refs inside the target
                return _resolve_refs(resolved, defs)
            return schema_node

        resolved_dict = {}
        for key, val in schema_node.items():
            if key == "$defs":
                continue
            resolved_dict[key] = _resolve_refs(val, defs)
        return resolved_dict

    elif isinstance(schema_node, list):
        return [_resolve_refs(item, defs) for item in schema_node]

    return schema_node


def _clean_mongo_schema_node(node: Any) -> Any:
    """
    Recursively transforms a JSON Schema node into a compliant MongoDB $jsonSchema node:
    - Converts 'type' to MongoDB 'bsonType'
    - Converts Optional (anyOf with null) to bsonType array containing 'null'
    - Strips unsupported keywords: title, default, examples, format, $schema
    - Enforces additionalProperties: False on objects
    """
    if not isinstance(node, dict):
        if isinstance(node, list):
            return [_clean_mongo_schema_node(item) for item in node]
        return node

    cleaned: Dict[str, Any] = {}

    # 1. Handle anyOf (commonly generated for Optional fields: [TargetType, null])
    if "anyOf" in node:
        branches = node["anyOf"]
        has_null = any(b.get("type") == "null" or b.get("bsonType") == "null" for b in branches if isinstance(b, dict))
        non_null_branches = [b for b in branches if isinstance(b, dict) and b.get("type") != "null" and b.get("bsonType") != "null"]

        if has_null and len(non_null_branches) == 1:
            # Simple Optional[T] -> extract non-null branch and add 'null' to bsonType
            inner = _clean_mongo_schema_node(non_null_branches[0])
            cleaned.update(inner)
            existing_type = cleaned.get("bsonType", "string")
            if isinstance(existing_type, list):
                if "null" not in existing_type:
                    cleaned["bsonType"] = existing_type + ["null"]
            else:
                cleaned["bsonType"] = [existing_type, "null"]
        else:
            # Complex anyOf
            cleaned["anyOf"] = [_clean_mongo_schema_node(b) for b in branches]

    # 2. Map primitive types to bsonType
    json_type = node.get("type")
    json_format = node.get("format")

    if json_format == "date-time" or json_type == "date":
        cleaned["bsonType"] = "date"
    elif json_type == "string":
        cleaned["bsonType"] = "string"
    elif json_type == "integer":
        cleaned["bsonType"] = ["int", "long"]
    elif json_type == "number":
        cleaned["bsonType"] = "number"
    elif json_type == "boolean":
        cleaned["bsonType"] = "bool"
    elif json_type == "array":
        cleaned["bsonType"] = "array"
        if "items" in node:
            cleaned["items"] = _clean_mongo_schema_node(node["items"])
    elif json_type == "object" or "properties" in node:
        cleaned["bsonType"] = "object"
        if "properties" in node:
            cleaned_props = {}
            for prop_name, prop_def in node["properties"].items():
                clean_prop = _clean_mongo_schema_node(prop_def)
                # Special handling for MongoDB _id primary key
                if prop_name == "_id":
                    clean_prop["bsonType"] = ["string", "objectId"]
                cleaned_props[prop_name] = clean_prop
            cleaned["properties"] = cleaned_props

        if "additionalProperties" in node:
            ap = node["additionalProperties"]
            if isinstance(ap, dict):
                cleaned["additionalProperties"] = _clean_mongo_schema_node(ap)
            elif isinstance(ap, bool):
                cleaned["additionalProperties"] = ap
        elif "properties" in node:
            cleaned["additionalProperties"] = False

    # 3. Carry over supported constraints
    for constraint_key in (
        "required",
        "enum",
        "pattern",
        "minimum",
        "maximum",
        "minLength",
        "maxLength",
        "minItems",
        "maxItems",
        "uniqueItems",
        "description",
    ):
        if constraint_key in node:
            val = node[constraint_key]
            cleaned[constraint_key] = copy.deepcopy(val)

    # Convert Draft 2020-12 exclusiveMinimum / exclusiveMaximum to Draft 4 (MongoDB BSON)
    if "exclusiveMinimum" in node:
        ex_min = node["exclusiveMinimum"]
        if isinstance(ex_min, (int, float)) and not isinstance(ex_min, bool):
            cleaned["minimum"] = ex_min
            cleaned["exclusiveMinimum"] = True
        elif isinstance(ex_min, bool):
            cleaned["exclusiveMinimum"] = ex_min

    if "exclusiveMaximum" in node:
        ex_max = node["exclusiveMaximum"]
        if isinstance(ex_max, (int, float)) and not isinstance(ex_max, bool):
            cleaned["maximum"] = ex_max
            cleaned["exclusiveMaximum"] = True
        elif isinstance(ex_max, bool):
            cleaned["exclusiveMaximum"] = ex_max

    # 4. Handle items if not handled above
    if "items" in node and "items" not in cleaned:
        cleaned["items"] = _clean_mongo_schema_node(node["items"])

    # 5. Default additionalProperties: False for object types with declared properties
    if cleaned.get("bsonType") == "object" and "additionalProperties" not in cleaned:
        if "properties" in cleaned:
            cleaned["additionalProperties"] = False

    return cleaned


def generate_mongo_schema(model_cls: Type[BaseModel]) -> Dict[str, Any]:
    """
    Converts a Pydantic v2 model class to a complete MongoDB $jsonSchema dictionary.
    
    The resulting dictionary is suitable for collection creation or collMod:
    {
        "$jsonSchema": {
            "bsonType": "object",
            "required": [...],
            "additionalProperties": False,
            "properties": { ... }
        }
    }
    """
    # Generate standard Pydantic JSON Schema
    raw_schema = model_cls.model_json_schema()
    defs = raw_schema.get("$defs", {})

    # Inline all references
    inlined_schema = _resolve_refs(raw_schema, defs)

    # Transform into MongoDB $jsonSchema compliant structure
    mongo_json_schema = _clean_mongo_schema_node(inlined_schema)

    # Ensure root object invariants
    mongo_json_schema["bsonType"] = "object"
    mongo_json_schema["additionalProperties"] = False

    # Ensure _id is defined in properties
    if "properties" in mongo_json_schema:
        if "_id" not in mongo_json_schema["properties"]:
            mongo_json_schema["properties"]["_id"] = {
                "bsonType": ["string", "objectId"],
                "description": "MongoDB document identifier",
            }
        if "id" in mongo_json_schema["properties"]:
            # If alias was used, remove redundant 'id' field definition if _id is present
            pass

    return {"$jsonSchema": mongo_json_schema}


# ── Canonical Collection to Storage Model Mapping ────────────────────────────

COLLECTION_STORAGE_MODELS: Dict[str, Type[BaseModel]] = {
    col.USERS: sm.UserStorage,
    col.IDENTITY_VAULT: sm.IdentityVaultStorage,
    col.CONSENT_NOTICES: sm.ConsentNoticeStorage,
    col.CONSENT_RECORDS: sm.ConsentRecordStorage,
    col.AUDIT_LOGS: sm.AuditLogStorage,
    col.COURSES: sm.CourseStorage,
    col.COURSE_WEEKS: sm.CourseWeekStorage,
    col.ENROLMENTS: sm.EnrolmentStorage,
    col.ASSIGNMENTS: sm.AssignmentStorage,
    col.SUBMISSIONS: sm.SubmissionStorage,
    col.QUIZZES: sm.QuizStorage,
    col.QUIZ_ATTEMPTS: sm.QuizAttemptStorage,
    col.GRADES: sm.GradeStorage,
    col.ATTENDANCE: sm.AttendanceStorage,
    col.ACTIVITY_EVENTS: sm.ActivityEventStorage,
    col.BEHAVIOR_WEEKLY: sm.BehaviorWeeklyStorage,
    col.MESSAGES: sm.TextMessageStorage,
    col.AFFECTIVE_WEEKLY: sm.AffectiveWeeklyStorage,
    col.ENGAGEMENT_TRAJECTORIES: sm.EngagementTrajectoryStorage,
    col.RISK_ASSESSMENTS: sm.RiskAssessmentStorage,
    col.RECOMMENDATIONS: sm.RecommendationStorage,
    col.INTERVENTIONS: sm.InterventionStorage,
    col.INTERVENTION_OUTCOMES: sm.InterventionOutcomeStorage,
    col.SCHEMA_MIGRATIONS: sm.SchemaMigrationStorage,
    col.INGESTION_RUNS: sm.IngestionRunStorage,
}

# Pre-compiled MongoDB $jsonSchema validator dictionary for each collection
COLLECTION_VALIDATORS: Dict[str, Dict[str, Any]] = {
    c: generate_mongo_schema(m) for c, m in COLLECTION_STORAGE_MODELS.items()
}
