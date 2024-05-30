app [makeGlue] {
    pf: platform "https://github.com/lukewilliamboswell/roc/releases/download/test/olBfrjtI-HycorWJMxdy7Dl2pcbbBoJy4mnSrDtRrlI.tar.br",
    glue: "https://github.com/lukewilliamboswell/roc-glue-code-gen/releases/download/0.2.0/UxzK668CtOpuhc_ipLgFC60pKqA7BVskJlHjEt7Snrg.tar.br",
}

import pf.Types exposing [Types]
import pf.File exposing [File]
import glue.Go

makeGlue : List Types -> Result (List File) Str
makeGlue = \_ -> Ok staticFiles

## These are always included, and don't depend on the specifics of the app.
staticFiles : List File
staticFiles =
    import "roc_app_templates/app.go" as appModule : Str
    import "roc_app_templates/app.h" as appHeader : Str

    List.concat Go.builtins [
        { name: "roc/app.go", content: appModule },
        { name: "roc/app.h", content: appHeader },
    ]
