"""Checks on the generated Shortcut file.

We cannot run Shortcuts here, so these tests verify the things that would
silently break the file: malformed variable tokens, an empty lookup table, a
save destination that does not match the configured library, and a plist that
will not round-trip.
"""

import plistlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from articlefiler.publications import PublicationRegistry
from shortcut.build_shortcut import (  # noqa: E402
    TOKEN,
    build_actions,
    build_shortcut,
    root_domain_map,
    title_suffix_pattern,
    token_string,
)


class TokenStringTests(unittest.TestCase):
    def test_plain_text_has_no_attachments(self):
        result = token_string("hello")
        self.assertEqual(result["Value"]["string"], "hello")
        self.assertEqual(result["Value"]["attachmentsByRange"], {})

    def test_a_variable_is_anchored_at_its_placeholder(self):
        result = token_string("Filed ", {"Type": "Variable", "VariableName": "FileName"})
        self.assertEqual(result["Value"]["string"], "Filed " + TOKEN)
        self.assertEqual(list(result["Value"]["attachmentsByRange"]), ["{6, 1}"])

    def test_every_attachment_offset_points_at_a_placeholder(self):
        result = token_string({"Type": "Variable", "VariableName": "A"}, " - ",
                              {"Type": "Variable", "VariableName": "B"})
        string = result["Value"]["string"]
        for span in result["Value"]["attachmentsByRange"]:
            offset = int(span.strip("{}").split(",")[0])
            self.assertEqual(string[offset], TOKEN)


class ShortcutStructureTests(unittest.TestCase):
    def setUp(self):
        self.registry = PublicationRegistry.bundled()
        self.workflow = build_shortcut(self.registry, "/Articles")
        self.actions = self.workflow["WFWorkflowActions"]

    def test_it_round_trips_as_a_binary_plist(self):
        reloaded = plistlib.loads(plistlib.dumps(self.workflow, fmt=plistlib.FMT_BINARY))
        self.assertEqual(len(reloaded["WFWorkflowActions"]), len(self.actions))

    def test_it_is_a_share_sheet_action(self):
        self.assertEqual(self.workflow["WFWorkflowTypes"], ["ActionExtension"])
        self.assertIn("WFURLContentItem", self.workflow["WFWorkflowInputContentItemClasses"])
        self.assertIn("WFSafariWebPageContentItem",
                      self.workflow["WFWorkflowInputContentItemClasses"])

    def test_every_action_has_an_identifier(self):
        for act in self.actions:
            self.assertTrue(act["WFWorkflowActionIdentifier"].startswith("is.workflow.actions."))

    def test_it_ends_by_making_naming_and_saving_a_pdf(self):
        tail = [a["WFWorkflowActionIdentifier"] for a in self.actions[-4:]]
        self.assertEqual(
            tail,
            [
                "is.workflow.actions.makepdf",
                "is.workflow.actions.setname",
                "is.workflow.actions.documentpicker.save",
                "is.workflow.actions.notification",
            ],
        )

    def test_the_save_destination_is_the_configured_folder(self):
        save = next(a for a in self.actions
                    if a["WFWorkflowActionIdentifier"].endswith("documentpicker.save"))
        self.assertEqual(save["WFWorkflowActionParameters"]["WFFileDestinationPath"], "/Articles")
        self.assertFalse(save["WFWorkflowActionParameters"]["WFAskWhereToSave"],
                         "it must not prompt — the whole point is that it is one tap")

    def test_every_variable_is_set_before_it_is_read(self):
        defined = set()
        for act in self.actions:
            params = act["WFWorkflowActionParameters"]
            if act["WFWorkflowActionIdentifier"].endswith("setvariable"):
                defined.add(params["WFVariableName"])
                continue
            for name in self._variables_used(params):
                self.assertIn(name, defined, f"{name} is read before it is set")

    def _variables_used(self, node) -> list:
        found = []
        if isinstance(node, dict):
            if node.get("Type") == "Variable" and "VariableName" in node:
                found.append(node["VariableName"])
            for value in node.values():
                found.extend(self._variables_used(value))
        elif isinstance(node, list):
            for value in node:
                found.extend(self._variables_used(value))
        return found

    def test_the_domain_lookup_table_is_populated(self):
        dictionaries = [a for a in self.actions
                        if a["WFWorkflowActionIdentifier"].endswith(".dictionary")]
        self.assertEqual(len(dictionaries), 2, "exact-host and root-domain tables")
        for act in dictionaries:
            items = act["WFWorkflowActionParameters"]["WFItems"]["Value"][
                "WFDictionaryFieldValueItems"
            ]
            self.assertGreater(len(items), 20)

    def test_the_exact_host_table_maps_real_domains(self):
        exact = next(a for a in self.actions
                     if a["WFWorkflowActionIdentifier"].endswith(".dictionary"))
        items = exact["WFWorkflowActionParameters"]["WFItems"]["Value"]["WFDictionaryFieldValueItems"]
        mapping = {i["WFKey"]["Value"]["string"]: i["WFValue"]["Value"]["string"] for i in items}
        self.assertEqual(mapping["wsj.com"], "WSJ")
        self.assertEqual(mapping["economist.com"], "TE")


class LookupTableTests(unittest.TestCase):
    def setUp(self):
        self.registry = PublicationRegistry.bundled()

    def test_root_domains_are_reduced_to_two_labels(self):
        mapping = root_domain_map(self.registry)
        self.assertEqual(mapping["nytimes.com"], "NYT")
        self.assertEqual(mapping["indiatimes.com"], "ET")  # first registered wins

    def test_the_title_suffix_pattern_matches_a_real_headline(self):
        import re

        pattern = re.compile(title_suffix_pattern(self.registry))
        self.assertEqual(pattern.sub("", "Fed holds rates - WSJ"), "Fed holds rates")
        self.assertEqual(pattern.sub("", "Grid storage | The Economist"), "Grid storage")

    def test_the_title_suffix_pattern_leaves_ordinary_headlines_alone(self):
        import re

        pattern = re.compile(title_suffix_pattern(self.registry))
        self.assertEqual(pattern.sub("", "A headline - with a dash"), "A headline - with a dash")


class ActionListTests(unittest.TestCase):
    def test_there_are_no_branches(self):
        actions = build_actions(PublicationRegistry.bundled(), "/Articles")
        identifiers = [a["WFWorkflowActionIdentifier"] for a in actions]
        self.assertNotIn("is.workflow.actions.conditional", identifiers)
        self.assertNotIn("is.workflow.actions.repeat.each", identifiers)


if __name__ == "__main__":
    unittest.main()
