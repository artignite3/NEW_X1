# Test suite

These `unittest` modules use fixed inputs, mocks and temporary stores for scoring, feature leakage, optimizer constraints, provider squad reuse, backup recovery, account isolation, explanation faithfulness, pipeline releases and launcher behavior. They are not substitutes for live Supabase provider/RLS checks, public tunnel access, or future-fixture accuracy evaluation.

From the repository root after `pip install -r requirements.txt`, run `python -m unittest discover -s tests -p 'test_*.py' -v`. CI runs this on Windows and Linux; frontend lint/build are separate. The [verification report](../docs/audit/VERIFICATION.md) distinguishes a fully provisioned run from import failures in an incomplete environment. Add a regression test when changing a contract or recovery path. See [CI workflows](../.github/workflows/README.md).
