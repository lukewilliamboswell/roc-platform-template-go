app [makeGlue] {
    pf: platform "https://github.com/lukewilliamboswell/roc/releases/download/test/olBfrjtI-HycorWJMxdy7Dl2pcbbBoJy4mnSrDtRrlI.tar.br",
    glue: "https://github.com/lukewilliamboswell/roc-glue-code-gen/releases/download/0.1.0/NprKi63CKBinQjoke2ttsOTHmjmsrmsILzRgzlds02c.tar.br",
}

import pf.Types exposing [Types]
import pf.File exposing [File]
import glue.Go

makeGlue : List Types -> Result (List File) Str
makeGlue = \_ -> Ok staticFiles

## These are always included, and don't depend on the specifics of the app.
staticFiles : List File
staticFiles =
    import "roc_app_templates/main.go" as appModule : Str
    import "roc_app_templates/main.h" as appHeader : Str

    List.concat Go.builtins [
        { name: "roc_app/main.go", content: appModule },
        { name: "roc_app/main.h", content: appHeader },
    ]
