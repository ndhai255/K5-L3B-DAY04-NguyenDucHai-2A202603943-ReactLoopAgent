"""Tests cho các kiểm tra thêm ở vòng cải tiến 2: incident ID chưa đọc và giới hạn retry 429."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agent import INCIDENT_ID_RE, run_agent
from bonus.tools import BonusTools
from status_tools import StatusTools
from test_lab import FakeProvider, tool_call, final


class IncidentGateTests(unittest.TestCase):
    def test_regex_matches_ids_not_words(self):
        self.assertEqual(INCIDENT_ID_RE.findall('Xem h02n9572mx9y và yaa0witbl2me, operational'),
                         ['h02n9572mx9y', 'yaa0witbl2me'])
        self.assertEqual(INCIDENT_ID_RE.findall('incident totally-not-a-real-id investigating'), [])

    def test_unread_incident_gets_one_reminder(self):
        url = 'https://stspg.io/pjgptg3cfc6n'
        fake = FakeProvider([final('Chưa đọc'),
                             tool_call('1', 'get_incident_details', '{"provider":"github","incident_id":"xr3myzj7ms51"}'),
                             final('Đã đọc. ' + url)])
        result = run_agent('Xem incident xr3myzj7ms51', fake, StatusTools(), max_steps=4)
        self.assertEqual(result['status'], 'completed')
        events = [t['event'] for t in result['trace']]
        self.assertEqual(events.count('validation_unread_incident'), 1)
        self.assertIn('xr3myzj7ms51', fake.histories[1][-1]['content'])

    def test_reminder_is_not_repeated(self):
        fake = FakeProvider([final('Không đọc'), final('Vẫn không đọc')])
        result = run_agent('Xem incident xr3myzj7ms51', fake, StatusTools(), max_steps=4)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['answer'], 'Vẫn không đọc')

    def test_failed_lookup_counts_as_attempted(self):
        fake = FakeProvider([tool_call('1', 'get_incident_details', '{"provider":"github","incident_id":"abc123def456"}'),
                             final('Không tìm thấy')])
        result = run_agent('Xem incident abc123def456', fake, StatusTools(), max_steps=3)
        self.assertEqual(result['status'], 'completed')
        self.assertNotIn('validation_unread_incident', [t['event'] for t in result['trace']])


class RetryLimitTests(unittest.TestCase):
    def test_persistent_429_is_blocked_after_three_real_calls(self):
        calls = [tool_call(str(i), 'get_vercel_status', '{}') for i in range(5)]
        fake = FakeProvider(calls + [final('Không xác định được Vercel')])
        result = run_agent('Kiểm tra Vercel', fake, BonusTools(scenario='rate_limit_always'), max_steps=8)
        self.assertEqual(result['status'], 'completed')
        real = [t for t in result['trace'] if t['event'] == 'tool']
        blocked = [t for t in result['trace'] if t['event'] == 'tool_blocked']
        self.assertEqual(len(real), 3)
        self.assertEqual(len(blocked), 2)
        self.assertEqual(json.loads(fake.histories[-1][-1]['content'])['error'], 'RETRY_LIMIT_REACHED')


if __name__ == '__main__':
    unittest.main()
