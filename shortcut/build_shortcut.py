#!/usr/bin/env python3
"""Generate the "File Article" Shortcut as an (unsigned) .shortcut plist.

Shortcuts files are property lists describing a list of actions. This script
builds that list from the same publication registry the Mac side uses, so the
acronyms you see on your iPhone are the acronyms the Mac agrees with.

    python3 shortcut/build_shortcut.py --out build/

Then, on a Mac, sign it so it can be opened on the iPhone:

    shortcuts sign --mode anyone --input build/File\\ Article.shortcut \\
                   --output build/File\\ Article.signed.shortcut

`shortcut/sign.sh` does that for you.
"""

from __future__ import annotations

import argparse
import plistlib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from articlefiler.config import Config  # noqa: E402
from articlefiler.publications import PublicationRegistry  # noqa: E402

# The placeholder character Shortcuts uses to anchor a variable inside a string.
TOKEN = "￼"


# -- serialisation helpers ---------------------------------------------


def variable(name: str) -> dict:
    """A reference to a named variable, e.g. the one Set Variable created."""
    return {"Type": "Variable", "VariableName": name}


def shortcut_input() -> dict:
    """A reference to whatever was shared into the Shortcut."""
    return {"Type": "ExtensionInput"}


def attachment(value: dict) -> dict:
    return {"WFSerializationType": "WFTextTokenAttachment", "Value": value}


def token_string(*parts) -> dict:
    """Build a text field that interpolates variables.

    Pass strings for literal text and attachment `Value` dicts for variables:
        token_string("Filed ", variable("FileName"))
    """
    string = ""
    attachments: dict[str, dict] = {}
    for part in parts:
        if isinstance(part, str):
            string += part
        else:
            attachments[f"{{{len(string)}, 1}}"] = part
            string += TOKEN
    return {
        "WFSerializationType": "WFTextTokenString",
        "Value": {"string": string, "attachmentsByRange": attachments},
    }


def action(identifier: str, **parameters) -> dict:
    return {
        "WFWorkflowActionIdentifier": identifier,
        "WFWorkflowActionParameters": parameters,
    }


# -- individual actions -------------------------------------------------


def set_variable(name: str) -> dict:
    """Store the previous action's output under `name`."""
    return action("is.workflow.actions.setvariable", WFVariableName=name)


def detect_link(source: dict) -> dict:
    return action("is.workflow.actions.detect.link", WFInput=attachment(source))


def first_item() -> dict:
    """Take the first item of the previous action's list output."""
    return action("is.workflow.actions.getitemfromlist", WFItemSpecifier="First Item")


def replace_text(source: dict, find: str, replace: str = "", regex: bool = True) -> dict:
    return action(
        "is.workflow.actions.text.replace",
        WFInput=attachment(source),
        WFReplaceTextFind=token_string(find),
        WFReplaceTextReplace=token_string(replace),
        WFReplaceTextRegularExpression=regex,
        WFReplaceTextCaseSensitive=False,
    )


def dictionary(mapping: dict[str, str]) -> dict:
    items = [
        {"WFItemType": 0, "WFKey": token_string(key), "WFValue": token_string(value)}
        for key, value in sorted(mapping.items())
    ]
    return action(
        "is.workflow.actions.dictionary",
        WFItems={
            "WFSerializationType": "WFDictionaryFieldValue",
            "Value": {"WFDictionaryFieldValueItems": items},
        },
    )


def dictionary_value(source: dict, key: dict) -> dict:
    return action(
        "is.workflow.actions.getvalueforkey",
        WFInput=attachment(source),
        WFDictionaryKey=token_string(key),
        WFGetDictionaryValueType="Value",
    )


def get_name(source: dict) -> dict:
    return action("is.workflow.actions.getitemname", WFInput=attachment(source))


def text(*parts) -> dict:
    return action("is.workflow.actions.gettext", WFTextActionText=token_string(*parts))


def make_pdf(source: dict) -> dict:
    return action(
        "is.workflow.actions.makepdf",
        WFInput=attachment(source),
        WFMakePDFIncludeMargin=False,
        WFMakePDFPaperSize="A4",
    )


def set_name(name: dict) -> dict:
    return action(
        "is.workflow.actions.setname",
        WFName=token_string(name),
        WFDontIncludeFileExtension=True,
    )


def save_file(destination: str, overwrite: bool = False) -> dict:
    return action(
        "is.workflow.actions.documentpicker.save",
        WFFileDestinationPath=destination,
        WFAskWhereToSave=False,
        WFSaveFileOverwrite=overwrite,
    )


def notify(*parts) -> dict:
    return action(
        "is.workflow.actions.notification",
        WFNotificationActionBody=token_string(*parts),
        WFNotificationActionTitle=token_string("Article filed"),
        WFNotificationActionSound=False,
    )


# -- the shortcut itself ------------------------------------------------

# Publication names that sites append to their own headlines. Kept as one
# regex so the whole clean-up is a single action.
def _escape(text: str) -> str:
    """Escape a publication name for use inside a regex alternation.

    `re.escape` rather than hand-rolled replacements: a name like "Which?" or
    "C++ Report" would otherwise turn its punctuation into quantifiers, which
    silently stops the suffix matching (and ICU, which drives Shortcuts'
    regular expressions, may reject it outright). Spaces are un-escaped again
    because `\ ` is noise in the pattern the user has to read.
    """
    return re.escape(text).replace("\\ ", " ")


def _suffix_alternatives(registry: PublicationRegistry) -> str:
    """Every publication name, longest first so the specific ones win."""
    suffixes = [s for pub in registry for s in pub.title_suffixes]
    suffixes.sort(key=len, reverse=True)
    return "|".join(_escape(s) for s in suffixes)


def title_suffix_pattern(registry: PublicationRegistry) -> str:
    """Matches the " - The Economist" a site appends to its own headlines."""
    return r"\s*[|–—·•-]\s*(?:" + _suffix_alternatives(registry) + r")\s*$"


def title_publisher_pattern(registry: PublicationRegistry) -> str:
    """Captures just the publisher's name out of a headline.

    A title that does not end in a known publication passes through unchanged,
    which then simply misses in the lookup dictionary — no branch needed.
    """
    return r"^(?:.*[|–—·•-]\s*)?(" + _suffix_alternatives(registry) + r")\s*$"


def publisher_name_map(registry: PublicationRegistry) -> dict[str, str]:
    """{publication name: acronym}, for identifying a paper from its title."""
    mapping: dict[str, str] = {}
    for pub in registry:
        for suffix in pub.title_suffixes:
            mapping.setdefault(suffix, pub.acronym)
    return mapping


def root_domain_map(registry: PublicationRegistry) -> dict[str, str]:
    """Domains reduced to their last two labels, for a second-chance lookup."""
    mapping: dict[str, str] = {}
    for pub in registry:
        for domain in pub.domains:
            labels = domain.split(".")
            root = ".".join(labels[-2:]) if len(labels) > 2 else domain
            mapping.setdefault(root, pub.acronym)
    return mapping


def build_actions(registry: PublicationRegistry, destination: str) -> list[dict]:
    """The whole flow, as a flat list of actions with no branching.

    Branchless on purpose: an `If` block in a generated Shortcut is fragile,
    and every case we would branch on can be handled by a regular expression
    on the composed text instead.
    """
    return [
        # 1. What did we get? Pull the article URL out of the shared item.
        detect_link(shortcut_input()),
        first_item(),
        set_variable("ArticleURL"),

        # 2. Reduce the URL to a host, then to a registrable domain.
        replace_text(variable("ArticleURL"),
                     r"^\s*[a-z]+://(?:www\.|m\.|amp\.|mobile\.)?([^/?#:]+).*$", "$1"),
        set_variable("Host"),
        replace_text(variable("Host"), r"^.*?([^.]+\.[^.]+)$", "$1"),
        set_variable("RootHost"),

        # 3. Look the host up in the publication table, exact host first.
        dictionary(registry.domain_map()),
        set_variable("PubMap"),
        dictionary_value(variable("PubMap"), variable("Host")),
        set_variable("AcronymExact"),
        dictionary(root_domain_map(registry)),
        set_variable("RootMap"),
        dictionary_value(variable("RootMap"), variable("RootHost")),
        set_variable("AcronymRoot"),

        # 4. The headline, as the share sheet reported it.
        get_name(shortcut_input()),
        set_variable("RawTitle"),

        # 5. Papers sign their own headlines ("... | Financial Times"), so the
        #    title identifies the publication when the URL cannot — an Apple
        #    News link, or a paper whose domain is not in the table yet.
        replace_text(variable("RawTitle"), title_publisher_pattern(registry), "$1"),
        set_variable("PublisherGuess"),
        dictionary(publisher_name_map(registry)),
        set_variable("NameMap"),
        dictionary_value(variable("NameMap"), variable("PublisherGuess")),
        set_variable("AcronymTitle"),

        # 6. Take whichever of the three lookups answered, with no If block.
        text(variable("AcronymExact"), " ", variable("AcronymRoot"), " ",
             variable("AcronymTitle")),
        set_variable("AcronymRaw"),
        replace_text(variable("AcronymRaw"), r"^\s+", ""),
        set_variable("AcronymTrimmed"),
        replace_text(variable("AcronymTrimmed"), r"\s.*$", ""),
        set_variable("Acronym"),

        # 7. Clean the headline up for use as a filename.
        replace_text(variable("RawTitle"), title_suffix_pattern(registry), ""),
        set_variable("TitleNoPublisher"),
        replace_text(variable("TitleNoPublisher"), r"[/\\:*?\"<>|#\[\]]", "-"),
        set_variable("TitleSafe"),
        replace_text(variable("TitleSafe"), r"\s{2,}", " "),
        set_variable("Title"),

        # 8. "<ACRONYM> - <Title>", collapsing the gap if nothing was found.
        text(variable("Acronym"), " - ", variable("Title")),
        set_variable("NameRaw"),
        replace_text(variable("NameRaw"), r"^\s*-\s*", ""),
        set_variable("NameTrimmed"),
        replace_text(variable("NameTrimmed"), r"\s*-\s*$", ""),
        set_variable("FileName"),

        # 9. Render, name, file.
        make_pdf(shortcut_input()),
        set_name(variable("FileName")),
        save_file(destination),
        notify(variable("FileName")),
    ]


def build_shortcut(registry: PublicationRegistry, destination: str) -> dict:
    workflow = {
        "WFWorkflowClientVersion": "2607.0.3",
        "WFWorkflowMinimumClientVersion": 900,
        "WFWorkflowMinimumClientVersionString": "900",
        "WFWorkflowHasShortcutInputVariables": True,
        "WFWorkflowIcon": {
            "WFWorkflowIconStartColor": 946986751,
            "WFWorkflowIconGlyphNumber": 59511,
        },
        "WFWorkflowImportQuestions": [],
        "WFWorkflowTypes": ["ActionExtension"],
        # Mac surfaces. iOS ignores this key; omitting it leaves the Shortcut
        # invisible in Services, Finder and Safari's share menu on the Mac.
        "WFQuickActionSurfaces": ["Services", "Finder"],
        "WFWorkflowInputContentItemClasses": [
            "WFArticleContentItem",
            "WFImageContentItem",
            "WFPDFContentItem",
            "WFRichTextContentItem",
            "WFSafariWebPageContentItem",
            "WFStringContentItem",
            "WFURLContentItem",
            "WFWebPageContentItem",
        ],
        "WFWorkflowActions": build_actions(registry, destination),
    }
    return workflow


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default="build", help="output directory")
    parser.add_argument("--destination", help="iCloud Drive path to save into")
    parser.add_argument("--name", default="File Article", help="shortcut file name")
    args = parser.parse_args(argv)

    config = Config.load()
    destination = args.destination or config.icloud_relative_library
    registry = PublicationRegistry.load([Path.home() / ".config/article-filer/publications.json"])

    out_dir = Path(args.out).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)

    workflow = build_shortcut(registry, destination)
    target = out_dir / f"{args.name}.shortcut"
    target.write_bytes(plistlib.dumps(workflow, fmt=plistlib.FMT_BINARY))

    readable = out_dir / f"{args.name}.plist"
    readable.write_bytes(plistlib.dumps(workflow, fmt=plistlib.FMT_XML))

    print(f"wrote {target}  ({len(workflow['WFWorkflowActions'])} actions)")
    print(f"wrote {readable}  (readable copy)")
    print(f"save destination: {destination}")
    print(f"publications:     {len(registry)}")
    print()
    print("Sign it on a Mac before opening it on the iPhone:")
    print(f"  ./shortcut/sign.sh '{target}'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
