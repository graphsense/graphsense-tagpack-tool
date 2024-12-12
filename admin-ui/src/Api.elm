module Api exposing (Data(..), baseUrl)

import Http


baseUrl : String
baseUrl =
    ""


type Data value
    = Loading
    | Success value
    | Failure Http.Error
