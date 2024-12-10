module Pages.Home_ exposing (Model, Msg, page)

import Api
import Api.Stats
import Dict
import Html exposing (Html)
import Html.Attributes
import Http
import Page exposing (Page)
import View exposing (View)


page : Page Model Msg
page =
    Page.element
        { init = init
        , update = update
        , subscriptions = subscriptions
        , view = view
        }



-- INIT


type alias Model =
    { stats : Api.Data Api.Stats.Stats
    }


init : ( Model, Cmd Msg )
init =
    ( { stats = Api.Loading }
    , Api.Stats.loadTagstoreStats
        { onResponse = TagstoreStatsResponded
        }
    )



-- UPDATE


type Msg
    = NoOp
    | TagstoreStatsResponded (Result Http.Error Api.Stats.Stats)


update : Msg -> Model -> ( Model, Cmd Msg )
update msg model =
    case msg of
        NoOp ->
            ( model
            , Cmd.none
            )

        TagstoreStatsResponded (Ok r) ->
            ( { model | stats = Api.Success r }, Cmd.none )

        TagstoreStatsResponded (Err r) ->
            ( { model | stats = Api.Failure r }, Cmd.none )



-- SUBSCRIPTIONS


subscriptions : Model -> Sub Msg
subscriptions model =
    Sub.none



-- VIEW


view : Model -> View Msg
view model =
    { title = "Tagstore Admin UI"
    , body =
        let
            networkToSpan ( network, stats ) =
                Html.span [ Html.Attributes.class "tag" ]
                    [ Html.text (network ++ " (" ++ String.fromInt stats.nr_tags ++ ")") ]
        in
        case model.stats of
            Api.Loading ->
                [ Html.text "Loading..." ]

            Api.Failure _ ->
                [ Html.text "There was an error fetching data..." ]

            Api.Success data ->
                [ Html.div [ Html.Attributes.class "tags" ]
                    (Dict.toList data.by_network
                        |> List.sortWith (\( _, a ) ( _, b ) -> compare a.nr_tags b.nr_tags)
                        |> List.map networkToSpan
                    )
                ]
    }
