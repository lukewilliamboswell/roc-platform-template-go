platform ""
    requires {} { main : MainForHost }
    exposes []
    packages {}
    imports []
    provides [mainForHost]

MainForHost : Str

mainForHost : MainForHost
mainForHost = main