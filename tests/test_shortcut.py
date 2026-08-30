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
    build_simple_shortcut,
    publisher_name_map,
    root_domain_map,
    title_publisher_pattern,
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
                "is.workflow.actions.setitemname",
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
        self.assertEqual(
            len(dictionaries), 3, "exact-host, root-domain and publisher-name tables"
        )
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
        self.assertEqual(mapping["economist.com"], "Economist")


class LookupTableTests(unittest.TestCase):
    def setUp(self):
        self.registry = PublicationRegistry.bundled()

    def test_publisher_names_map_to_acronyms(self):
        mapping = publisher_name_map(self.registry)
        self.assertEqual(mapping["Financial Times"], "FT")
        self.assertEqual(mapping["The Economist"], "Economist")

    def test_the_publisher_pattern_captures_the_paper_from_a_headline(self):
        import re

        pattern = re.compile(title_publisher_pattern(self.registry), re.IGNORECASE)
        self.assertEqual(
            pattern.sub(r"\1", "The heat pump decade | Financial Times"), "Financial Times"
        )

    def test_the_publisher_pattern_leaves_an_unsigned_headline_alone(self):
        import re

        pattern = re.compile(title_publisher_pattern(self.registry), re.IGNORECASE)
        headline = "A headline with no publisher"
        # Unchanged, so it simply misses in the dictionary lookup.
        self.assertEqual(pattern.sub(r"\1", headline), headline)

    def test_a_publication_name_with_regex_metacharacters_is_escaped(self):
        import re

        from articlefiler.publications import Publication

        registry = PublicationRegistry.bundled()
        registry.add(Publication("WCH", "Which?", ("which.co.uk",), ("Which? (C++ Report)",)))
        pattern = re.compile(title_suffix_pattern(registry), re.IGNORECASE)
        self.assertEqual(pattern.sub("", "Best heat pumps - Which? (C++ Report)"),
                         "Best heat pumps")

    def test_root_domains_are_reduced_to_two_labels(self):
        mapping = root_domain_map(self.registry)
        self.assertEqual(mapping["nytimes.com"], "NYT")
        self.assertEqual(mapping["indiatimes.com"], "EconomicTimes")  # first registered wins

    def test_the_title_suffix_pattern_matches_a_real_headline(self):
        import re

        pattern = re.compile(title_suffix_pattern(self.registry))
        self.assertEqual(pattern.sub("", "Fed holds rates - WSJ"), "Fed holds rates")
        self.assertEqual(pattern.sub("", "Grid storage | The Economist"), "Grid storage")

    def test_the_title_suffix_pattern_leaves_ordinary_headlines_alone(self):
        import re

        pattern = re.compile(title_suffix_pattern(self.registry))
        self.assertEqual(pattern.sub("", "A headline - with a dash"), "A headline - with a dash")


class ActionIdentifierTests(unittest.TestCase):
    """Shortcuts refuses to run a shortcut containing an unknown action, with
    only "an action could not be found" to go on — so the identifiers are
    worth asserting explicitly rather than assuming."""

    KNOWN = {
        "is.workflow.actions.detect.link",
        "is.workflow.actions.dictionary",
        "is.workflow.actions.documentpicker.save",
        "is.workflow.actions.getitemfromlist",
        "is.workflow.actions.getitemname",
        "is.workflow.actions.gettext",
        "is.workflow.actions.getvalueforkey",
        "is.workflow.actions.makepdf",
        "is.workflow.actions.notification",
        "is.workflow.actions.setitemname",
        "is.workflow.actions.setvariable",
        "is.workflow.actions.text.replace",
    }

    def test_only_known_identifiers_are_used(self):
        used = {a["WFWorkflowActionIdentifier"]
                for a in build_actions(PublicationRegistry.bundled(), "/Articles")}
        self.assertEqual(used - self.KNOWN, set(), "unverified action identifier")

    def test_get_and_set_name_are_the_matching_pair(self):
        # "setname" does not exist; Set Name pairs with Get Name as setitemname.
        used = {a["WFWorkflowActionIdentifier"]
                for a in build_actions(PublicationRegistry.bundled(), "/Articles")}
        self.assertIn("is.workflow.actions.getitemname", used)
        self.assertIn("is.workflow.actions.setitemname", used)
        self.assertNotIn("is.workflow.actions.setname", used)


class SimpleVariantTests(unittest.TestCase):
    def setUp(self):
        self.workflow = build_simple_shortcut("/Articles/_Inbox")

    def test_it_is_three_actions(self):
        self.assertEqual(len(self.workflow["WFWorkflowActions"]), 3)

    def test_it_uses_only_the_most_stable_actions(self):
        used = [a["WFWorkflowActionIdentifier"] for a in self.workflow["WFWorkflowActions"]]
        self.assertEqual(used, ["is.workflow.actions.makepdf",
                                "is.workflow.actions.documentpicker.save",
                                "is.workflow.actions.notification"])

    def test_it_saves_into_the_inbox_for_the_watcher_to_rename(self):
        save = self.workflow["WFWorkflowActions"][1]["WFWorkflowActionParameters"]
        self.assertEqual(save["WFFileDestinationPath"], "/Articles/_Inbox")
        self.assertFalse(save["WFAskWhereToSave"])

    def test_it_is_still_a_share_sheet_action(self):
        self.assertEqual(self.workflow["WFWorkflowTypes"], ["ActionExtension"])


class ActionListTests(unittest.TestCase):
    def test_there_are_no_branches(self):
        actions = build_actions(PublicationRegistry.bundled(), "/Articles")
        identifiers = [a["WFWorkflowActionIdentifier"] for a in actions]
        self.assertNotIn("is.workflow.actions.conditional", identifiers)
        self.assertNotIn("is.workflow.actions.repeat.each", identifiers)


if __name__ == "__main__":
    unittest.main()


class AskingVariantTests(unittest.TestCase):
    """The diagnostic variant. Every other shortcut writes to a destination it
    cannot verify; this one puts the result in front of the user, so a silent
    save failure becomes visible."""

    def setUp(self):
        from shortcut.build_shortcut import build_asking_shortcut

        self.workflow = build_asking_shortcut("/Articles")

    def test_it_is_two_actions(self):
        self.assertEqual(len(self.workflow["WFWorkflowActions"]), 2)

    def test_it_renders_then_saves(self):
        used = [a["WFWorkflowActionIdentifier"] for a in self.workflow["WFWorkflowActions"]]
        self.assertEqual(used, ["is.workflow.actions.makepdf",
                                "is.workflow.actions.documentpicker.save"])

    def test_it_asks_where_to_save(self):
        save = self.workflow["WFWorkflowActions"][1]["WFWorkflowActionParameters"]
        self.assertTrue(save["WFAskWhereToSave"], "the whole point is that it prompts")

    def test_it_has_no_notification_to_give_false_comfort(self):
        used = [a["WFWorkflowActionIdentifier"] for a in self.workflow["WFWorkflowActions"]]
        self.assertNotIn("is.workflow.actions.notification", used)

    def test_the_other_variants_still_do_not_ask(self):
        from shortcut.build_shortcut import build_shortcut, build_simple_shortcut

        for workflow in (build_shortcut(PublicationRegistry.bundled(), "/Articles"),
                         build_simple_shortcut("/Articles/_Inbox")):
            save = next(a for a in workflow["WFWorkflowActions"]
                        if a["WFWorkflowActionIdentifier"].endswith("documentpicker.save"))
            self.assertFalse(save["WFWorkflowActionParameters"]["WFAskWhereToSave"])
