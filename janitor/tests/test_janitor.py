"""
Unit tests for Cost Janitor helper functions.
Run with: pytest janitor/tests/
"""

import sys
import os
from datetime import datetime, timezone, timedelta

# Add parent directory so we can import janitor modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from janitor import tags_to_dict, missing_tags, age_days, is_protected, ebs_monthly_cost
from constants import REQUIRED_TAGS, EBS_GP3_USD_PER_GB_MONTH, EBS_GP2_USD_PER_GB_MONTH


class TestTagsToDict:
    def test_empty_list(self):
        assert tags_to_dict([]) == {}

    def test_none(self):
        assert tags_to_dict(None) == {}

    def test_normal(self):
        result = tags_to_dict([{"Key": "Project", "Value": "nimbuskart"}])
        assert result == {"Project": "nimbuskart"}

    def test_multiple(self):
        tags = [{"Key": "Project", "Value": "A"}, {"Key": "Owner", "Value": "devops"}]
        result = tags_to_dict(tags)
        assert result["Project"] == "A"
        assert result["Owner"] == "devops"


class TestMissingTags:
    def test_all_present(self):
        tag_dict = {"Project": "A", "Environment": "staging", "Owner": "team"}
        assert missing_tags(tag_dict) == []

    def test_one_missing(self):
        tag_dict = {"Project": "A", "Environment": "staging"}
        result = missing_tags(tag_dict)
        assert "Owner" in result

    def test_all_missing(self):
        result = missing_tags({})
        assert set(result) == set(REQUIRED_TAGS)

    def test_empty_value_counts_as_missing(self):
        tag_dict = {"Project": "", "Environment": "staging", "Owner": "team"}
        result = missing_tags(tag_dict)
        assert "Project" in result


class TestAgeDays:
    def test_today(self):
        now = datetime.now(timezone.utc)
        assert age_days(now) == 0

    def test_twenty_one_days_ago(self):
        dt = datetime.now(timezone.utc) - timedelta(days=21)
        assert age_days(dt) == 21

    def test_one_day_ago(self):
        dt = datetime.now(timezone.utc) - timedelta(hours=25)
        assert age_days(dt) == 1


class TestIsProtected:
    def test_protected_true(self):
        assert is_protected({"Protected": "true"}) is True

    def test_protected_True_uppercase(self):
        assert is_protected({"Protected": "True"}) is True

    def test_not_protected(self):
        assert is_protected({"Protected": "false"}) is False

    def test_no_key(self):
        assert is_protected({}) is False


class TestEbsMonthlyCost:
    def test_gp3_10gb(self):
        vol = {"Size": 10, "VolumeType": "gp3"}
        expected = round(EBS_GP3_USD_PER_GB_MONTH * 10, 2)
        assert ebs_monthly_cost(vol) == expected

    def test_gp2_20gb(self):
        vol = {"Size": 20, "VolumeType": "gp2"}
        expected = round(EBS_GP2_USD_PER_GB_MONTH * 20, 2)
        assert ebs_monthly_cost(vol) == expected

    def test_unknown_type_defaults_to_gp3(self):
        vol = {"Size": 10, "VolumeType": "io1"}
        expected = round(EBS_GP3_USD_PER_GB_MONTH * 10, 2)
        assert ebs_monthly_cost(vol) == expected
