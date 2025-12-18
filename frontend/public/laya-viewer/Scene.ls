{
    "_$ver": 1,
    "_$id": "264nou51",
    "_$type": "Scene",
    "left": 0,
    "right": 0,
    "top": 0,
    "bottom": 0,
    "name": "Scene2D",
    "width": 1334,
    "height": 750,
    "_$child": [
        {
            "_$id": "n9gjxcltvl",
            "_$type": "Scene3D",
            "name": "Scene3D",
            "skyRenderer": {
                "meshType": "dome",
                "material": {
                    "_$uuid": "sky.lmat",
                    "_$type": "Material"
                }
            },
            "ambientMode": 1,
            "ambientSH": {
                "_$type": "Float32Array",
                "value": [
                    0.561861515045166,
                    0.5691413879394531,
                    0.5156031250953674,
                    0.25098922848701477,
                    0.29723599553108215,
                    0.3360276222229004,
                    0.18643078207969666,
                    0.16357596218585968,
                    0.11102143675088882,
                    -0.5348716974258423,
                    -0.507384181022644,
                    -0.4003814160823822,
                    -0.24370312690734863,
                    -0.22358225286006927,
                    -0.1722458302974701,
                    0.11344613134860992,
                    0.10041586309671402,
                    0.07283135503530502,
                    -0.04577554389834404,
                    -0.036940183490514755,
                    -0.020133458077907562,
                    -0.28794020414352417,
                    -0.2579245865345001,
                    -0.19256529211997986,
                    0.20134146511554718,
                    0.1833409070968628,
                    0.1309514194726944
                ]
            },
            "ambientColor": {
                "_$type": "Color",
                "r": 0.424308,
                "g": 0.4578516,
                "b": 0.5294118
            },
            "_reflectionsIblSamples": 1024,
            "iblTex": {
                "_$uuid": "Scene/Scene.ktx",
                "_$type": "TextureCube"
            },
            "iblTexRGBD": true,
            "fogStart": 0,
            "fogEnd": 300,
            "fogColor": {
                "_$type": "Color",
                "r": 0.5,
                "g": 0.5,
                "b": 0.5
            },
            "_$child": [
                {
                    "_$id": "6jx8h8bvc6",
                    "_$type": "Camera",
                    "name": "Main Camera",
                    "transform": {
                        "localPosition": {
                            "_$type": "Vector3",
                            "y": 1,
                            "z": 5
                        }
                    },
                    "nearPlane": 0.3,
                    "farPlane": 1000,
                    "clearFlag": 1,
                    "clearColor": {
                        "_$type": "Color",
                        "r": 0.3921,
                        "g": 0.5843,
                        "b": 0.9294
                    }
                },
                {
                    "_$id": "6ni3p096l5",
                    "_$type": "LightSprite",
                    "name": "Direction Light",
                    "transform": {
                        "localPosition": {
                            "_$type": "Vector3",
                            "x": 5,
                            "y": 5,
                            "z": 5
                        },
                        "localRotation": {
                            "_$type": "Quaternion",
                            "x": -0.40821789367673483,
                            "y": 0.23456971600980447,
                            "z": 0.109381654946615,
                            "w": 0.875426098065593
                        }
                    },
                    "_$comp": [
                        {
                            "_$type": "DirectionLightCom",
                            "strength": 1,
                            "angle": 0.526,
                            "maxBounces": 1024
                        }
                    ]
                },
                {
                    "_$id": "gq6c2zg9",
                    "_$prefab": "model.glb",
                    "name": "model",
                    "active": true,
                    "layer": 0,
                    "transform": {
                        "localPosition": {
                            "_$type": "Vector3"
                        },
                        "localRotation": {
                            "_$type": "Quaternion"
                        }
                    }
                }
            ]
        }
    ]
}