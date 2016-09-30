import os
from unittest import TestCase
from unittest.mock import mock_open, patch
from environment import read_env, env_var


class TestEnv(TestCase):
    def test_read_env(self):
        mo = mock_open()
        with patch('environment.open', mo, create=True):
            mo().read.return_value =\
                '''should_be_true=True
should_be_false=False
should_be_three=3
single_quoted='test1'
double_quoted="test2"
'''
            read_env()
        self.assertTrue(env_var('should_be_true'))
        self.assertFalse(env_var('should_be_false'))
        self.assertEqual(env_var('should_be_three'), '3')
        self.assertEqual(env_var('single_quoted'), 'test1')
        self.assertEqual(env_var('double_quoted'), 'test2')

    def test_env_var_true_conversion(self):
        os.environ['test'] = 'True'
        self.assertTrue(env_var('test'))

    def test_env_var_false_conversion(self):
        os.environ['test'] = 'False'
        self.assertFalse(env_var('test'))
