# Licensing status

## V2 implementation

The new V2 implementation under `src/` is licensed under the MIT License in
[`src/stocks_investment/LICENSE`](src/stocks_investment/LICENSE). The package
metadata also declares `MIT`.

This grant applies only to the contents of `src/`. It does not grant rights to
any historical file inherited from upstream commit
`8d87bece9fe0e87f8f654511aec713d1b3b98175`, including the legacy directories
`Functions and Libs/`, `mainCode/`, and `Test/`.

## Historical upstream code

The upstream repository did not declare a license when it was forked. A public
request for the original author to confirm MIT terms is tracked in
[galanCA/Stocks-and-Investment#28](https://github.com/galanCA/Stocks-and-Investment/issues/28).

Until the copyright holder gives explicit permission, the historical upstream
files remain outside the V2 MIT grant and must not be included in a V2 source or
binary distribution. Public availability and the ability to fork a repository
do not by themselves create an open-source license.

## Response playbook

The upstream response must be handled as follows:

| Upstream response | Required action |
| --- | --- |
| Adds an MIT license upstream | Verify that the license covers the historical code, record the upstream commit, preserve its copyright notice, and then replace this scoped arrangement with a repository-wide license notice. |
| Explicitly agrees to MIT in the issue | Ask the author to add the license upstream, or submit a minimal license-only pull request for explicit acceptance. Keep the current scope until that change is merged. |
| Requests a pull request | Submit only the standard MIT license and the original author's copyright line; do not mix modernization changes into that pull request. Expand the local scope only after upstream accepts it. |
| Chooses Apache-2.0 or a BSD license | Check the exact license and notices, then retain MIT for V2 while complying with the compatible upstream license and attribution requirements. |
| Chooses GPL, AGPL, another copyleft license, or custom terms | Do not combine or redistribute the two codebases until compatibility and contributor permissions have been reviewed. Prefer keeping V2 independent of the historical code. |
| Refuses permission | Exclude the historical code from releases and migration work. Continue V2 as an independent MIT implementation, without copying protected expression from the legacy files. |
| Says another person also owns rights | Obtain permission from every relevant copyright holder before changing the historical code's licensing status. |
| Gives an ambiguous or conditional answer | Ask for the exact license name, version, scope, copyright holder, and conditions. Do not treat informal approval as a license grant. |
| Does not respond | Treat the historical code as unlicensed. Package and distribute only V2 material covered by an explicit license. |

## Financial-information disclaimer

Licensing does not make the software or its outputs financial advice. Releases
and user-facing documentation should separately state that the software is for
research and informational purposes, may contain errors, and does not replace
professional financial advice.
