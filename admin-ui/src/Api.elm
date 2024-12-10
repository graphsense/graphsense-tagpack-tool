module Api exposing (Data(..))

import Http


type Data value
    = Loading
    | Success value
    | Failure Http.Error
