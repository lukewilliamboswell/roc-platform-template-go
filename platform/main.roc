platform ""
    requires {} { main! : {} => Result {} [Exit I32 Str]_ }
    exposes [Stdout]
    packages {}
    imports [Stdout]
    provides [mainForHost!]

mainForHost! : I32 => Result {} I32
mainForHost! = \_ ->
    when main! {} is
        Ok {} -> Ok {}
        Err (Exit code str) ->
            if Str.isEmpty str then
                Err code
            else
                when Stdout.line! str is
                    Ok {} -> Err code
                    Err _ -> Err code

        Err err ->
            when Stdout.line! "Program exited early with error: $(Inspect.toStr err)" is
                Ok {} -> Err 1
                Err _ -> Err 1
