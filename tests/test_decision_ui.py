import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest


class DecisionUITests(unittest.TestCase):
    def test_notebook_validation(self):
        from v7_ui import validate_notebook
        notebook={"version":1,"symbol":" test ","inputs":{"growth":8},"holdings":[],"evidence":[]}
        restored=validate_notebook(notebook)
        self.assertEqual(restored["symbol"],"TEST")
        self.assertEqual(restored["inputs"]["growth"],8)
        self.assertEqual(restored["inputs"]["years"],5)
        for bad in ([], dict(notebook,holdings="bad"),dict(notebook,observations=[]),
                    dict(notebook,holdings=[{"Symbol":"TEST","Sector":"Tech","Value":-1}]),
                    dict(notebook,inputs={"ffo_per_share":3})):
            with self.subTest(value=bad), self.assertRaises(ValueError): validate_notebook(bad)

    def test_failed_notebook_keeps_last_report_and_downloads(self):
        code='''
import sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/"tests"))
from test_decision_report import fixture
import streamlit as st
import v7_ui
import importlib
importlib.reload(v7_ui)
v7_ui.complete_stock_research=lambda *args: fixture()
if st.checkbox("Simulate notebook failure"):
    def fail(*args): raise ValueError("Notebook serialization failed")
    v7_ui._notebook=fail
v7_ui.render()
'''
        app=AppTest.from_string(code,default_timeout=30).run()
        next(b for b in app.button if b.label=="Run complete research").click().run()
        self.assertEqual(len(app.error),0)
        old_pdf=app.session_state["v7_pdf"]
        old_notebook=app.session_state["decision_notebook"]
        app.text_input(key="v7_symbol").set_value("TEST").run()
        app.number_input(key="dr_growth").set_value(9).run()
        app.checkbox[0].check().run()
        next(b for b in app.button if b.label=="Rebuild report with current assumptions").click().run()
        self.assertTrue(any("Notebook serialization failed" in e.value for e in app.error))
        self.assertEqual(app.session_state["v7_report"]["decision"]["assumptions"]["growth"],5)
        self.assertEqual(app.session_state["v7_pdf"],old_pdf)
        self.assertEqual(app.session_state["decision_notebook"],old_notebook)

    def test_generation_rebuild_and_missing_data(self):
        # Fixture data isolates interactions from remote market-data availability.
        code='''
import sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/"tests"))
from test_decision_report import fixture
import v7_ui
import importlib
importlib.reload(v7_ui)
def research(symbol,*args):
    report=fixture()
    report["symbol"]=symbol
    report["snapshot"]["Symbol"]=symbol
    return report
v7_ui.complete_stock_research=research
v7_ui.render()
'''
        app=AppTest.from_string(code,default_timeout=30).run()
        self.assertEqual(len(app.exception),0)
        next(b for b in app.button if b.label=="Run complete research").click().run()
        self.assertEqual(len(app.exception),0)
        self.assertEqual(len(app.error),0)
        self.assertEqual(app.session_state["v7_report"]["decision"]["assumptions"]["growth"],5)
        app.number_input(key="dr_growth").set_value(9).run()
        next(b for b in app.button if b.label=="Rebuild report with current assumptions").click().run()
        self.assertEqual(len(app.error),0)
        self.assertEqual(app.session_state["v7_report"]["decision"]["assumptions"]["growth"],9)
        app.number_input(key="dr_terminal_growth").set_value(12).run()
        next(b for b in app.button if b.label=="Rebuild report with current assumptions").click().run()
        self.assertTrue(any("exceed terminal growth" in e.value for e in app.error))
        self.assertEqual(app.session_state["v7_report"]["decision"]["assumptions"]["terminal_growth"],2.5)


if __name__=="__main__": unittest.main()
