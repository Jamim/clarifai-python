import os
import time
import typing

import pytest
from google.protobuf import struct_pb2

from clarifai.client.search import Search
from clarifai.client.user import User
from clarifai.errors import UserError

CREATE_APP_USER_ID = os.environ["CLARIFAI_USER_ID"]
now = int(time.time())
CREATE_APP_ID = f"ci_search_app_{now}"
CREATE_DATASET_ID = "ci_search_dataset"
DOG_IMG_URL = "https://samples.clarifai.com/dog.tiff"
DATASET_IMAGES_DIR = os.path.dirname(__file__) + "/assets/voc/images"


def get_filters_for_test() -> [(typing.List[typing.Dict], int)]:
  return [
      ([{
          "geo_point": {
              "longitude": -29.0,
              "latitude": 40.0,
              "geo_limit": 10
          }
      }], 1),
      ([{
          "concepts": [{
              "name": "dog",
              "value": 1
          }]
      }], 1),
      (
          [{  # OR
              "concepts": [{
                  "name": "deer",
                  "value": 1
              }, {
                  "name": "dog",
                  "value": 1
              }]
          }],
          1),
      (
          [
              {  # AND
                  "concepts": [{
                      "name": "dog",
                      "value": 1
                  }]
              },
              {
                  "concepts": [{
                      "name": "deer",
                      "value": 1
                  }]
              }
          ],
          0),
    (
        [

                {
                "metadata": {"Breed": "Saint Bernard"}
                }
        ],
        1),

      # Input Search
      (
            [
                { # AND
                  "input_types": ["image"],
                },
                {
                  "input_status_code": 30000 # Download Success
                }
            ],
            1),
      (
            [
                {
                  "input_types": ["text", "audio", "video"],
                }
            ],
            0),
      (
            [
                { # OR
                  "input_types": ["text", "audio", "video"],
                  "input_status_code": 30000 # Download Success
                },
            ],
            1),
      (
            [
                {
                  "input_dataset_ids": ["random_dataset"]
                },
            ],
            0),
  ]


class TestAnnotationSearch:

  @classmethod
  def setup_class(cls):
    cls.client = User(user_id=CREATE_APP_USER_ID)
    cls.search = Search(
        user_id=CREATE_APP_USER_ID, app_id=CREATE_APP_ID, top_k=1, metric="euclidean")
    cls.upload_data()

  @classmethod
  def upload_data(self):
    app_obj = self.client.create_app(CREATE_APP_ID, base_workflow="General")
    dataset_obj = app_obj.create_dataset(CREATE_DATASET_ID)
    inp_obj = app_obj.inputs()
    metadata = struct_pb2.Struct()
    metadata.update({"Breed": "Saint Bernard"})
    input_proto = inp_obj.get_input_from_url(
        dataset_id=CREATE_DATASET_ID,
        input_id="dog-tiff",
        image_url=DOG_IMG_URL,
        labels=["dog"],
        geo_info=[-30.0, 40.0],  # longitude, latitude
        metadata=metadata)
    inp_obj.upload_inputs([input_proto])
    dataset_obj.upload_from_folder(DATASET_IMAGES_DIR, input_type="image", labels=False)

  @pytest.mark.parametrize("filter_dict_list,expected_hits", get_filters_for_test())
  def test_filter_search(self, filter_dict_list: typing.List[typing.Dict], expected_hits: int):
    query = self.search.query(filters=filter_dict_list)
    for q in query:
      assert len(q.hits) == expected_hits

  def test_rank_search(self):
    query = self.search.query(ranks=[{"image_url": "https://samples.clarifai.com/dog.tiff"}])
    for q in query:
      assert len(q.hits) == 1
      assert q.hits[0].input.id == "dog-tiff"

  def test_schema_error(self):
    with pytest.raises(UserError):
      _ = self.search.query(filters=[{
          "geo_point": {
              "longitude": -29.0,
              "latitude": 40.0,
              "geo_limit": 10,
              "extra": 1
          }
      }])

    # Incorrect Concept Keys
    with pytest.raises(UserError):
      _ = self.search.query(filters=[{
          "concepts": [{
              "value": 1,
              "concept_id": "deer"
          }, {
              "name": "dog",
              "value": 1
          }]
      }])

    # Incorrect Concept Values
    with pytest.raises(UserError):
      _ = self.search.query(filters=[{
          "concepts": [{
              "name": "deer",
              "value": 2
          }, {
              "name": "dog",
              "value": 1
          }]
      }])

    # Incorrect input type search
    with pytest.raises(UserError):
      _ = self.search.query(filters=[{"input_types": ["imaage"]}])

    # Incorrect input search filter key
    with pytest.raises(UserError):
      _ = self.search.query(filters=[{"input_id": "test"}])

  def teardown_class(cls):
    cls.client.delete_app(app_id=CREATE_APP_ID)
