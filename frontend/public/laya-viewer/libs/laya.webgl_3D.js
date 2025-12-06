(function (exports, Laya) {
    'use strict';

    class RenderCullUtil {
        static cullByCameraCullInfo(cameraCullInfo, list, count, opaqueList, transparent, context) {
            const boundFrustum = cameraCullInfo.boundFrustum;
            const cullMask = cameraCullInfo.cullingMask;
            const staticMask = cameraCullInfo.staticMask;
            let render;
            let canPass;
            for (let i = 0; i < count; i++) {
                render = list[i];
                canPass = ((1 << render.layer) & cullMask) != 0 && (render.renderbitFlag == 0);
                canPass = canPass && ((render.staticMask & staticMask) != 0);
                if (canPass) {
                    if (!cameraCullInfo.useOcclusionCulling || render._needRender(boundFrustum)) {
                        render.distanceForSort = Laya.Vector3.distanceSquared(render.bounds._imp.getCenter(), cameraCullInfo.position);
                        render._renderUpdatePre(context);
                        let element;
                        const elements = render.renderelements;
                        for (let j = 0, len = elements.length; j < len; j++) {
                            element = elements[j];
                            if (element.materialRenderQueue > 2500)
                                transparent.addRenderElement(element);
                            else
                                opaqueList.addRenderElement(element);
                        }
                    }
                }
            }
        }
        static cullDirectLightShadow(shadowCullInfo, list, count, opaqueList, context) {
            opaqueList.clear();
            for (let i = 0; i < count; i++) {
                const render = list[i];
                if (render.shadowCullPass()) {
                    if (Laya.FrustumCulling.cullingRenderBounds(render.bounds, shadowCullInfo)) {
                        render.distanceForSort = Laya.Vector3.distanceSquared(render.bounds._imp.getCenter(), shadowCullInfo.position);
                        render._renderUpdatePre(context);
                        let element;
                        const elements = render.renderelements;
                        for (let j = 0, len = elements.length; j < len; j++) {
                            element = elements[j];
                            if (element.materialRenderQueue < 2500)
                                opaqueList.addRenderElement(element);
                        }
                    }
                }
            }
        }
        static cullSpotShadow(cameraCullInfo, list, count, opaqueList, context) {
            opaqueList.clear();
            const boundFrustum = cameraCullInfo.boundFrustum;
            for (let i = 0; i < count; i++) {
                const render = list[i];
                render._renderUpdatePre(context);
                if (render.shadowCullPass()) {
                    render.distanceForSort = Laya.Vector3.distanceSquared(render.bounds._imp.getCenter(), cameraCullInfo.position);
                    if (render._needRender(boundFrustum)) {
                        let element;
                        const elements = render.renderelements;
                        for (let j = 0, len = elements.length; j < len; j++) {
                            element = elements[j];
                            if (element.materialRenderQueue < 2500)
                                opaqueList.addRenderElement(element);
                        }
                    }
                }
            }
        }
    }

    class RenderPassUtil {
        static renderCmd(cmds, context) {
            if (cmds && cmds.length > 0)
                cmds.forEach(value => context.runCMDList(value._renderCMDs));
        }
        static recoverRenderContext3D(context, renderTarget) {
            context.setViewPort(this.contextViewPortCache);
            context.setScissor(this.contextScissorCache);
            context.setRenderTarget(renderTarget, Laya.RenderClearFlag.Nothing);
        }
    }
    RenderPassUtil.contextViewPortCache = new Laya.Viewport();
    RenderPassUtil.contextScissorCache = new Laya.Vector4();

    class RenderQuickSort {
        sort(elements, isTransparent, left, right) {
            this.elementArray = elements;
            this.isTransparent = isTransparent;
            this._quickSort(left, right);
        }
        _quickSort(left, right) {
            if (this.elementArray.length > 1) {
                const index = this._partitionRenderObject(left, right);
                const leftIndex = index - 1;
                if (left < leftIndex)
                    this._quickSort(left, leftIndex);
                if (index < right)
                    this._quickSort(index, right);
            }
        }
        _partitionRenderObject(left, right) {
            const elements = this.elementArray.elements;
            const pivot = elements[Math.floor((right + left) / 2)];
            while (left <= right) {
                while (this._compare(elements[left], pivot) < 0)
                    left++;
                while (this._compare(elements[right], pivot) > 0)
                    right--;
                if (left < right) {
                    const temp = elements[left];
                    elements[left] = elements[right];
                    elements[right] = temp;
                    left++;
                    right--;
                }
                else if (left === right) {
                    left++;
                    break;
                }
            }
            return left;
        }
        _compare(left, right) {
            const renderQueue = left.materialRenderQueue - right.materialRenderQueue;
            if (renderQueue === 0) {
                const sort = this.isTransparent ? right.owner.distanceForSort - left.owner.distanceForSort : left.owner.distanceForSort - right.owner.distanceForSort;
                return sort + right.owner.sortingFudge - left.owner.sortingFudge;
            }
            else
                return renderQueue;
        }
    }

    class RenderListQueue {
        get elements() { return this._elements; }
        constructor(isTransParent) {
            this._elements = new Laya.FastSinglelist();
            this._isTransparent = isTransParent;
            this._quickSort = new RenderQuickSort();
            this._batch = Laya.Laya3DRender.Render3DPassFactory.createInstanceBatch();
        }
        addRenderElement(renderelement) {
            renderelement.materialShaderData && this._elements.add(renderelement);
        }
        _batchQueue() {
            if (!this._isTransparent) {
                let time = performance.now();
                this._batch.batch(this._elements);
                Laya.LayaGL.statAgent.recordTimeData(Laya.StatElement.T_3DBatchTime, performance.now() - time);
            }
        }
        renderQueue(context) {
            this._batchQueue();
            const count = this._elements.length;
            this._quickSort.sort(this._elements, this._isTransparent, 0, count - 1);
            context.drawRenderElementList(this._elements);
            Laya.LayaGL.statAgent.recordCTData(this._isTransparent ? Laya.StatElement.CT_TransDrawCall : Laya.StatElement.CT_OpaqueDrawCall, this.elements.length);
            this._batch.clearRenderData();
        }
        clear() {
            this._elements.elements.fill(null);
            this._elements.length = 0;
        }
        destroy() {
            this.clear();
            this._elements = null;
        }
    }

    class ForwardAddClusterRP {
        setViewPort(value) {
            value.cloneTo(this._viewPort);
        }
        setScissor(value) {
            value.cloneTo(this._scissor);
        }
        constructor() {
            this._opaqueList = new RenderListQueue(false);
            this._transparent = new RenderListQueue(true);
            this.cameraCullInfo = new Laya.CameraCullInfo();
            this._zBufferParams = new Laya.Vector4();
            this._scissor = new Laya.Vector4();
            this._viewPort = new Laya.Viewport();
            this._defaultNormalDepthColor = new Laya.Color(0.5, 0.5, 1, 0);
            this.clearColor = new Laya.Color();
            this.depthPipelineMode = "ShadowCaster";
            this.depthNormalPipelineMode = "DepthNormal";
        }
        setCameraCullInfo(camera) {
            this.cameraCullInfo.position = camera._transform.position;
            this.cameraCullInfo.cullingMask = camera.cullingMask;
            this.cameraCullInfo.staticMask = camera.staticMask;
            this.cameraCullInfo.boundFrustum = camera.boundFrustum;
            this.cameraCullInfo.useOcclusionCulling = camera.useOcclusionCulling;
        }
        setBeforeForwardCmds(value) {
            if (value && value.length > 0) {
                this.beforeForwardCmds = value;
                value.forEach(element => element._apply(false));
            }
        }
        setBeforeSkyboxCmds(value) {
            if (value && value.length > 0) {
                this.beforeSkyboxCmds = value;
                value.forEach(element => element._apply(false));
            }
        }
        setBeforeTransparentCmds(value) {
            if (value && value.length > 0) {
                this.beforeTransparentCmds = value;
                value.forEach(element => element._apply(false));
            }
        }
        render(context, list, count) {
            context.cameraUpdateMask++;
            this._clearRenderList();
            var time = performance.now();
            RenderCullUtil.cullByCameraCullInfo(this.cameraCullInfo, list, count, this._opaqueList, this._transparent, context);
            Laya.LayaGL.statAgent.recordTimeData(Laya.StatElement.T_CullMain, performance.now() - time);
            time = performance.now();
            if ((this.depthTextureMode & Laya.DepthTextureMode.Depth) != 0)
                this._renderDepthPass(context);
            if ((this.depthTextureMode & Laya.DepthTextureMode.DepthNormals) != 0)
                this._renderDepthNormalPass(context);
            Laya.LayaGL.statAgent.recordTimeData(Laya.StatElement.T_DepthPass, performance.now() - time);
            this._cacheViewPortAndScissor();
            time = performance.now();
            this._mainPass(context);
            Laya.LayaGL.statAgent.recordTimeData(Laya.StatElement.T_3DMainPass, performance.now() - time);
            this._opaqueList._batch.recoverData();
        }
        _clearRenderList() {
            this._opaqueList.clear();
            this._transparent.clear();
        }
        _cacheViewPortAndScissor() {
            this._viewPort.cloneTo(RenderPassUtil.contextViewPortCache);
            this._scissor.cloneTo(RenderPassUtil.contextScissorCache);
        }
        _renderDepthPass(context) {
            context.pipelineMode = this.depthPipelineMode;
            const viewport = this._viewPort;
            const shadervalue = context.sceneData;
            shadervalue.addDefine(Laya.DepthPass.DEPTHPASS);
            shadervalue.setVector(Laya.DepthPass.DEFINE_SHADOW_BIAS, Laya.Vector4.ZERO);
            Laya.Viewport.TEMP.set(viewport.x, viewport.y, viewport.width, viewport.height);
            Laya.Vector4.TEMP.setValue(viewport.x, viewport.y, viewport.width, viewport.height);
            context.setViewPort(Laya.Viewport.TEMP);
            context.setScissor(Laya.Vector4.TEMP);
            context.setRenderTarget(this.depthTarget, Laya.RenderClearFlag.Depth);
            context.setClearData(Laya.RenderClearFlag.Depth, Laya.Color.BLACK, 1, 0);
            this._opaqueList.renderQueue(context);
            Laya.LayaGL.statAgent.recordCTData(Laya.StatElement.CT_DepthCastDrawCall, this._opaqueList.elements.length);
            const far = this.camera.farPlane;
            const near = this.camera.nearPlane;
            this._zBufferParams.setValue(1.0 - far / near, far / near, (near - far) / (near * far), 1 / near);
            context.cameraData.setVector(Laya.DepthPass.DEFINE_SHADOW_BIAS, Laya.DepthPass.SHADOW_BIAS);
            context.cameraData.setVector(Laya.DepthPass.DEPTHZBUFFERPARAMS, this._zBufferParams);
            Laya.Camera.depthPass._setupDepthModeShaderValue(Laya.DepthTextureMode.Depth, this.camera);
            shadervalue.removeDefine(Laya.DepthPass.DEPTHPASS);
        }
        _renderDepthNormalPass(context) {
            context.pipelineMode = this.depthNormalPipelineMode;
            this.camera._shaderValues.setTexture(Laya.DepthPass.DEPTHNORMALSTEXTURE, Laya.Texture2D.blackTexture);
            const viewport = this._viewPort;
            Laya.Viewport.TEMP.set(viewport.x, viewport.y, viewport.width, viewport.height);
            Laya.Vector4.TEMP.setValue(viewport.x, viewport.y, viewport.width, viewport.height);
            context.setViewPort(Laya.Viewport.TEMP);
            context.setScissor(Laya.Vector4.TEMP);
            context.setClearData(Laya.RenderClearFlag.Color | Laya.RenderClearFlag.Depth, this._defaultNormalDepthColor, 1, 0);
            context.setRenderTarget(this.depthNormalTarget, Laya.RenderClearFlag.Color | Laya.RenderClearFlag.Depth);
            this._opaqueList.renderQueue(context);
            Laya.LayaGL.statAgent.recordCTData(Laya.StatElement.CT_DepthCastDrawCall, this._opaqueList.elements.length);
            Laya.Camera.depthPass._setupDepthModeShaderValue(Laya.DepthTextureMode.DepthNormals, this.camera);
        }
        _mainPass(context) {
            context.pipelineMode = this.pipelineMode;
            RenderPassUtil.renderCmd(this.beforeForwardCmds, context);
            RenderPassUtil.recoverRenderContext3D(context, this.destTarget);
            context.setClearData(this.clearFlag, this.clearColor, 1, 0);
            var time = performance.now();
            this._opaqueList.renderQueue(context);
            Laya.LayaGL.statAgent.recordTimeData(Laya.StatElement.T_3DMainPass_Opaque, performance.now() - time);
            RenderPassUtil.renderCmd(this.beforeSkyboxCmds, context);
            if (this.skyRenderNode) {
                const skyRenderElement = this.skyRenderNode.renderelements[0];
                if (skyRenderElement.subShader)
                    context.drawRenderElementOne(skyRenderElement);
            }
            if (this.enableOpaque)
                this._opaqueTexturePass();
            RenderPassUtil.renderCmd(this.beforeTransparentCmds, context);
            RenderPassUtil.recoverRenderContext3D(context, this.destTarget);
            time = performance.now();
            this._transparent.renderQueue(context);
            Laya.LayaGL.statAgent.recordTimeData(Laya.StatElement.T_3DMainPass_Trans, performance.now() - time);
        }
        _opaqueTexturePass() {
        }
    }

    class WebBaseRenderNode {
        get shaderData() {
            return this._shaderData;
        }
        set shaderData(value) {
            this._shaderData = value;
        }
        _renderUpdatePre(context3D) {
            if (this._updateMark == context3D.cameraUpdateMask)
                return;
            this._renderUpdatePreFun.call(this._renderUpdatePreCall, context3D);
            this._updateMark = context3D.cameraUpdateMask;
        }
        _calculateBoundingBox() {
            this._caculateBoundingBoxFun.call(this._caculateBoundingBoxCall);
        }
        get bounds() {
            if (this.boundsChange) {
                this._calculateBoundingBox();
                this.boundsChange = false;
            }
            return this._bounds;
        }
        set bounds(value) {
            this._bounds = value;
        }
        get additionShaderData() {
            return this._additionShaderData;
        }
        set additionShaderData(value) {
            this._additionShaderData = value;
            if (value) {
                this._additionShaderDataKeys = Array.from(this._additionShaderData.keys());
            }
            else {
                this._additionShaderDataKeys = [];
            }
        }
        constructor() {
            this.ismoved = new Laya.Vector2();
            this.renderelements = [];
            this._commonUniformMap = [];
            this._worldParams = new Laya.Vector4(1, 0, 0, 0);
            this.lightmapDirtyFlag = -1;
            this.lightmapScaleOffset = new Laya.Vector4(1, 1, 0, 0);
            this.set_caculateBoundingBox(this, this._ownerCalculateBoundingBox);
            this._additionShaderData = new Map();
        }
        setNodeCustomData(dataSlot, data) {
            switch (dataSlot) {
                case 0:
                    this._worldParams.y = data;
                    break;
                case 1:
                    this._worldParams.z = data;
                    break;
                case 2:
                    this._worldParams.w = data;
                    break;
            }
        }
        set_renderUpdatePreCall(call, fun) {
            this._renderUpdatePreCall = call;
            this._renderUpdatePreFun = fun;
        }
        set_caculateBoundingBox(call, fun) {
            this._caculateBoundingBoxCall = call;
            this._caculateBoundingBoxFun = fun;
        }
        _needRender(boundFrustum) {
            if (boundFrustum)
                return boundFrustum.intersects(this.bounds);
            else
                return true;
        }
        setRenderelements(value) {
            this.renderelements.length = 0;
            for (var i = 0; i < value.length; i++) {
                this.renderelements.push(value[i]);
                value[i].owner = this;
            }
        }
        setOneMaterial(index, mat) {
            if (!this.renderelements[index])
                return;
            this.renderelements[index].materialShaderData = mat.shaderData;
            this.renderelements[index].materialRenderQueue = mat.renderQueue;
            this.renderelements[index].subShader = mat.shader.getSubShaderAt(0);
            this.renderelements[index].materialId = mat._id;
        }
        setLightmapScaleOffset(value) {
            value && value.cloneTo(this.lightmapScaleOffset);
        }
        setCommonUniformMap(value) {
            this._commonUniformMap.length = 0;
            value.forEach(element => {
                this._commonUniformMap.push(element);
            });
        }
        shadowCullPass() {
            return this.castShadow && this.enable && (this.renderbitFlag == 0);
        }
        _ownerCalculateBoundingBox() {
            this.baseGeometryBounds._tranform(this.transform.worldMatrix, this._bounds);
        }
        _applyLightMapParams() {
            let shaderValues = this.shaderData;
            if (this.lightmap) {
                let lightMap = this.lightmap;
                shaderValues.setVector(Laya.RenderableSprite3D.LIGHTMAPSCALEOFFSET, this.lightmapScaleOffset);
                shaderValues._setInternalTexture(Laya.RenderableSprite3D.LIGHTMAP, lightMap.lightmapColor);
                shaderValues.addDefine(Laya.RenderableSprite3D.SAHDERDEFINE_LIGHTMAP);
                if (lightMap.lightmapDirection) {
                    shaderValues._setInternalTexture(Laya.RenderableSprite3D.LIGHTMAP_DIRECTION, lightMap.lightmapDirection);
                    shaderValues.addDefine(Laya.RenderableSprite3D.SHADERDEFINE_LIGHTMAP_DIRECTIONAL);
                }
                else {
                    shaderValues.removeDefine(Laya.RenderableSprite3D.SHADERDEFINE_LIGHTMAP_DIRECTIONAL);
                }
            }
            else {
                shaderValues.removeDefine(Laya.RenderableSprite3D.SAHDERDEFINE_LIGHTMAP);
                shaderValues.removeDefine(Laya.RenderableSprite3D.SHADERDEFINE_LIGHTMAP_DIRECTIONAL);
            }
        }
        _applyLightProb() {
            if (this.lightmapIndex >= 0 || !this.volumetricGI)
                return;
            if (this.volumetricGI.updateMark != this.lightProbUpdateMark) {
                this.lightProbUpdateMark = this.volumetricGI.updateMark;
                this.volumetricGI.applyRenderData();
            }
        }
        _applyReflection() {
            if (!this.probeReflection || this.reflectionMode == Laya.ReflectionProbeMode.off)
                return;
            if (this.probeReflection.needUpdate()) {
                this.probeReflection.applyRenderData();
            }
        }
        destroy() {
            this.renderelements.forEach(element => {
                element.destroy();
            });
            this.baseGeometryBounds = null;
            this.transform = null;
            this.lightmapScaleOffset = null;
            this.lightmap = null;
            this.probeReflection = null;
            this.volumetricGI = null;
            this.renderelements.length = 0;
            this.renderelements = null;
            this.shaderData && this.shaderData.destroy();
            this.shaderData = null;
            this._commonUniformMap.length = 0;
            this._commonUniformMap = null;
            this.additionShaderData.clear();
            this.additionShaderData = null;
            this._additionShaderDataKeys.length = 0;
            this._additionShaderDataKeys = null;
        }
    }

    class WebDirectLight {
        constructor() {
            this._shadowFourCascadeSplits = new Laya.Vector3();
            this._direction = new Laya.Vector3();
        }
        setShadowFourCascadeSplits(value) {
            value && value.cloneTo(this._shadowFourCascadeSplits);
        }
        setDirection(value) {
            value && value.cloneTo(this._direction);
        }
    }

    class WebLightmap {
        destroy() {
            this.lightmapColor = null;
            this.lightmapDirection = null;
        }
    }

    var CLS = null;
    function WebMeshRenderNode() {
        if (!CLS)
            CLS = class extends WebBaseRenderNode.BaseRenderNodeClass {
                constructor() {
                    super();
                    this._cacheMoved = new Laya.Vector2(-1, -1);
                    this.set_renderUpdatePreCall(this, this._renderUpdate);
                }
                _renderUpdate(context) {
                    if (context.sceneModuleData.lightmapDirtyFlag != this.lightmapDirtyFlag) {
                        this._applyLightMapParams();
                        this.lightmapDirtyFlag = context.sceneModuleData.lightmapDirtyFlag;
                    }
                    this._applyReflection();
                    this._applyLightProb();
                    if (this.ismoved.x > this._cacheMoved.x || (this.ismoved.x == this._cacheMoved.x && this.ismoved.y > this._cacheMoved.y)) {
                        let trans = this.transform;
                        this.shaderData.setMatrix4x4(Laya.Sprite3D.WORLDMATRIX, trans.worldMatrix);
                        this._worldParams.x = trans.getFrontFaceValue();
                        this.shaderData.setVector(Laya.Sprite3D.WORLDINVERTFRONT, this._worldParams);
                        this.ismoved.cloneTo(this._cacheMoved);
                    }
                }
            };
        return CLS;
    }

    class WebCameraNodeData {
        constructor() {
            this._projectViewMatrix = new Laya.Matrix4x4();
        }
        setProjectionViewMatrix(value) {
            value && value.cloneTo(this._projectViewMatrix);
        }
    }
    class WebSceneNodeData {
    }

    class WebPointLight {
    }

    class WebReflectionProbe {
        constructor() {
            this._id = ++WebReflectionProbe._idCounter;
            this._updateMaskFlag = -1;
            this._shCoefficients = [];
            this._probePosition = new Laya.Vector3();
            this._ambientColor = new Laya.Color();
            this.shaderData = Laya.LayaGL.renderDeviceFactory.createShaderData();
        }
        needUpdate() {
            return this.updateMark != this._updateMaskFlag;
        }
        destroy() {
            this.bound = null;
            delete this._shCoefficients;
            delete this._ambientSH;
            this.shaderData.destroy();
            this.shaderData = null;
        }
        setAmbientSH(value) {
            this._ambientSH = value;
        }
        setShCoefficients(value) {
            this._shCoefficients.length = 0;
            value.forEach(element => {
                var v4 = new Laya.Vector4();
                element.cloneTo(v4);
                this._shCoefficients.push(v4);
            });
        }
        setProbePosition(value) {
            value && value.cloneTo(this._probePosition);
        }
        setreflectionHDRParams(value) {
            value && value.cloneTo(this._reflectionHDRParams);
        }
        setAmbientColor(value) {
            value && value.cloneTo(this._ambientColor);
        }
        applyRenderData() {
            this._updateMaskFlag = this.updateMark;
            let data = this.shaderData;
            if (!this.boxProjection) {
                data.removeDefine(Laya.Sprite3DRenderDeclaration.SHADERDEFINE_SPECCUBE_BOX_PROJECTION);
            }
            else {
                data.addDefine(Laya.Sprite3DRenderDeclaration.SHADERDEFINE_SPECCUBE_BOX_PROJECTION);
                data.setVector3(Laya.ReflectionProbe.REFLECTIONCUBE_PROBEPOSITION, this._probePosition);
                data.setVector3(Laya.ReflectionProbe.REFLECTIONCUBE_PROBEBOXMAX, this.bound.getMax());
                data.setVector3(Laya.ReflectionProbe.REFLECTIONCUBE_PROBEBOXMIN, this.bound.getMin());
            }
            if (this.ambientMode == Laya.AmbientMode.SolidColor) {
                data.removeDefine(Laya.Sprite3DRenderDeclaration.SHADERDEFINE_GI_LEGACYIBL);
                data.removeDefine(Laya.ReflectionProbe.SHADERDEFINE_GI_IBL);
                data.setColor(Laya.ReflectionProbe.AMBIENTCOLOR, this._ambientColor);
            }
            else if (this.iblTex && this._ambientSH) {
                data.addDefine(Laya.ReflectionProbe.SHADERDEFINE_GI_IBL);
                data.removeDefine(Laya.Sprite3DRenderDeclaration.SHADERDEFINE_GI_LEGACYIBL);
                if (this.iblTex) {
                    data._setInternalTexture(Laya.ReflectionProbe.IBLTEX, this.iblTex);
                    data.setNumber(Laya.ReflectionProbe.IBLROUGHNESSLEVEL, this.iblTex.maxMipmapLevel);
                }
                this.iblTexRGBD ? data.addDefine(Laya.Sprite3DRenderDeclaration.SHADERDEFINE_IBL_RGBD) : data.removeDefine(Laya.Sprite3DRenderDeclaration.SHADERDEFINE_IBL_RGBD);
                this._ambientSH && data.setBuffer(Laya.ReflectionProbe.AMBIENTSH, this._ambientSH);
            }
            else {
                data.removeDefine(Laya.Sprite3DRenderDeclaration.SHADERDEFINE_GI_LEGACYIBL);
                data.removeDefine(Laya.ReflectionProbe.SHADERDEFINE_GI_IBL);
            }
            data.setNumber(Laya.ReflectionProbe.AMBIENTINTENSITY, this.ambientIntensity);
            data.setNumber(Laya.ReflectionProbe.REFLECTIONINTENSITY, this.reflectionIntensity);
        }
    }
    WebReflectionProbe._idCounter = 0;

    var CLSSK = null;
    function WebSkinRenderNode() {
        if (!CLSSK)
            CLSSK = class extends WebBaseRenderNode.BaseRenderNodeClass {
                constructor() {
                    super();
                    this._bones = [];
                    this.set_renderUpdatePreCall(this, this._renderUpdate);
                }
                setRootBoneTransfom(value) {
                    this._cacheRootBone = value.transform;
                }
                setOwnerTransform(value) {
                    this._owner = value.transform;
                }
                setCacheMesh(cacheMesh) {
                    this._cacheMesh = cacheMesh;
                    this._skinnedDataLoopMarks = new Uint32Array(cacheMesh._inverseBindPoses.length);
                }
                setBones(value) {
                    this._bones = value;
                }
                setSkinnedData(value) {
                    this._skinnedData = value;
                }
                computeSkinnedData() {
                    var bindPoses = this._cacheMesh._inverseBindPoses;
                    var pathMarks = this._cacheMesh._skinnedMatrixCaches;
                    for (var i = 0, n = this._cacheMesh.subMeshCount; i < n; i++) {
                        var subMeshBoneIndices = ((this._cacheMesh.getSubMesh(i)))._boneIndicesList;
                        var subData = this._skinnedData[i];
                        for (var j = 0, m = subMeshBoneIndices.length; j < m; j++) {
                            var boneIndices = subMeshBoneIndices[j];
                            this._computeSubSkinnedData(bindPoses, boneIndices, subData[j], pathMarks);
                        }
                    }
                }
                _computeSubSkinnedData(bindPoses, boneIndices, data, matrixCaches) {
                    for (let k = 0, q = boneIndices.length; k < q; k++) {
                        let index = boneIndices[k];
                        if (this._skinnedDataLoopMarks[index] === Laya.Stat.loopCount) {
                            let c = matrixCaches[index];
                            let preData = this._skinnedData[c.subMeshIndex][c.batchIndex];
                            let srcIndex = c.batchBoneIndex * 16;
                            let dstIndex = k * 16;
                            for (let d = 0; d < 16; d++)
                                data[dstIndex + d] = preData[srcIndex + d];
                        }
                        else {
                            let bone = this._bones[index];
                            if (bone)
                                Laya.Utils3D._mulMatrixArray(bone.transform.worldMatrix.elements, bindPoses[index].elements, 0, data, k * 16);
                            this._skinnedDataLoopMarks[index] = Laya.Stat.loopCount;
                        }
                    }
                }
                _renderUpdate(context3D) {
                    let mat = this._owner.worldMatrix;
                    let worldParams = this._worldParams;
                    worldParams.x = this._owner.getFrontFaceValue();
                    if (this._cacheRootBone) {
                        mat = Laya.Matrix4x4.DEFAULT;
                        worldParams.x = 1;
                    }
                    this._applyLightProb();
                    this._applyReflection();
                    this.shaderData.setMatrix4x4(Laya.Sprite3D.WORLDMATRIX, mat);
                    this.shaderData.setVector(Laya.Sprite3D.WORLDINVERTFRONT, worldParams);
                }
            };
        return CLSSK;
    }

    class WebSpotLight {
        setDirection(value) {
            value.cloneTo(this._direction);
        }
        getWorldMatrix(out) {
            var position = this.transform.position;
            var quaterian = this.transform.rotation;
            Laya.Matrix4x4.createAffineTransformation(position, quaterian, Laya.Vector3.ONE, out);
            return out;
        }
    }

    class WebVolumetricGI {
        constructor() {
            this._id = ++WebVolumetricGI._idCounter;
            this._probeCounts = new Laya.Vector3();
            this._probeStep = new Laya.Vector3();
            this._params = new Laya.Vector4();
            this._params = new Laya.Vector4();
            this.bound = new Laya.Bounds();
            this.shaderData = Laya.LayaGL.renderDeviceFactory.createShaderData();
        }
        setParams(value) {
            value.cloneTo(this._params);
        }
        setProbeCounts(value) {
            value.cloneTo(this._probeCounts);
        }
        setProbeStep(value) {
            value.cloneTo(this._probeStep);
        }
        applyRenderData() {
            let data = this.shaderData;
            data.addDefine(Laya.VolumetricGI.SHADERDEFINE_VOLUMETRICGI);
            data.setVector3(Laya.VolumetricGI.VOLUMETRICGI_PROBECOUNTS, this._probeCounts);
            data.setVector3(Laya.VolumetricGI.VOLUMETRICGI_PROBESTEPS, this._probeStep);
            data.setVector3(Laya.VolumetricGI.VOLUMETRICGI_PROBESTARTPOS, this.bound.getMin());
            data.setVector(Laya.VolumetricGI.VOLUMETRICGI_PROBEPARAMS, this._params);
            data._setInternalTexture(Laya.VolumetricGI.VOLUMETRICGI_IRRADIANCE, this.irradiance);
            data._setInternalTexture(Laya.VolumetricGI.VOLUMETRICGI_DISTANCE, this.distance);
            data.setNumber(Laya.ReflectionProbe.AMBIENTINTENSITY, this.intensity);
        }
        destroy() {
            this.shaderData.destroy();
            this.shaderData = null;
            this.irradiance = null;
            this.distance = null;
            this.bound = null;
        }
    }
    WebVolumetricGI._idCounter = 0;

    var CLASSIMPLESKIN = null;
    function WebSimpleSkinRenderNode() {
        if (!CLASSIMPLESKIN)
            CLASSIMPLESKIN = class extends WebBaseRenderNode.BaseRenderNodeClass {
                constructor() {
                    super();
                    this.set_renderUpdatePreCall(this, this._renderUpdate);
                    this._simpleAnimatorParams = new Laya.Vector4();
                }
                setSimpleAnimatorParams(value) {
                    value.cloneTo(this._simpleAnimatorParams);
                    this.shaderData.setVector(Laya.SimpleSkinnedMeshSprite3D.SIMPLE_SIMPLEANIMATORPARAMS, this._simpleAnimatorParams);
                }
                _renderUpdate(context3D) {
                    let shaderData = this.shaderData;
                    let worldMat = this.transform.worldMatrix;
                    let worldParams = this._worldParams;
                    worldParams.x = this.transform.getFrontFaceValue();
                    shaderData.setMatrix4x4(Laya.Sprite3D.WORLDMATRIX, worldMat);
                    shaderData.setVector(Laya.Sprite3D.WORLDINVERTFRONT, worldParams);
                    this._applyLightProb();
                    this._applyReflection();
                    shaderData.setVector(Laya.SimpleSkinnedMeshSprite3D.SIMPLE_SIMPLEANIMATORPARAMS, this._simpleAnimatorParams);
                }
            };
        return CLASSIMPLESKIN;
    }

    class Web3DRenderModuleFactory {
        createSimpleSkinRenderNode() {
            return new (WebSimpleSkinRenderNode())();
        }
        createTransform(owner) {
            return new Laya.Transform3D(owner);
        }
        createBounds(min, max) {
            return new Laya.BoundsImpl(min, max);
        }
        createVolumetricGI() {
            return new WebVolumetricGI();
        }
        createReflectionProbe() {
            return new WebReflectionProbe();
        }
        createLightmapData() {
            return new WebLightmap();
        }
        createDirectLight() {
            return new WebDirectLight();
        }
        createSpotLight() {
            return new WebSpotLight();
        }
        createPointLight() {
            return new WebPointLight();
        }
        createCameraModuleData() {
            return new WebCameraNodeData();
        }
        createSceneModuleData() {
            return new WebSceneNodeData();
        }
        createBaseRenderNode() {
            let renderNode = new WebBaseRenderNode();
            return renderNode;
        }
        createMeshRenderNode() {
            return new (WebMeshRenderNode())();
        }
        createSkinRenderNode() {
            return new (WebSkinRenderNode())();
        }
    }
    Laya.Laya.addBeforeInitCallback(() => {
        if (!Laya.Laya3DRender.Render3DModuleDataFactory) {
            Laya.Laya3DRender.Render3DModuleDataFactory = new Web3DRenderModuleFactory();
        }
    });

    class WebSceneRenderManager {
        constructor() {
            this._list = new Laya.SingletonList();
            this.baseRenderList = new Laya.SingletonList();
        }
        get list() {
            return this._list;
        }
        set list(value) {
            this._list = value;
            let elemnt = this._list.elements;
            this.baseRenderList.clear();
            for (let i = 0; i < this._list.length; i++) {
                this.baseRenderList.add(elemnt[i]._baseRenderNode);
            }
        }
        addRenderObject(object) {
            this._list.add(object);
            this.baseRenderList.add(object._baseRenderNode);
        }
        removeRenderObject(object) {
            this._list.remove(object);
            this.baseRenderList.remove(object._baseRenderNode);
        }
        removeMotionObject(object) {
        }
        updateMotionObjects() {
        }
        addMotionObject(object) {
        }
        destroy() {
            this._list.destroy();
            this.baseRenderList.destroy();
            this._list = null;
            this.baseRenderList = null;
        }
    }

    class WebGLInstanceRenderBatch {
        constructor() {
            this._batchOpaqueMarks = [];
            this._updateCountMark = 0;
            this.recoverList = new Laya.FastSinglelist();
        }
        getBatchMark(element) {
            const renderNode = element.owner;
            const geometry = element.geometry;
            const invertFrontFace = element.transform ? element.transform._isFrontFaceInvert : false;
            const invertFrontFaceFlag = invertFrontFace ? 1 : 0;
            const receiveShadowFlag = renderNode.receiveShadow ? 1 : 0;
            const geometryFlag = geometry._id;
            const materialFlag = element.materialId;
            const renderId = (materialFlag << 17) + (geometryFlag << 2) + (invertFrontFaceFlag << 1) + (receiveShadowFlag);
            const reflectFlag = (renderNode.probeReflection ? renderNode.probeReflection._id : -1) + 1;
            const lightmapFlag = renderNode.lightmapIndex + 1;
            const lightProbeFlag = (renderNode.volumetricGI ? renderNode.volumetricGI._id : -1) + 1;
            const giId = (reflectFlag << 10) + (lightmapFlag << 20) + lightProbeFlag;
            const data = this._batchOpaqueMarks[renderId] || (this._batchOpaqueMarks[renderId] = {});
            return data[giId] || (data[giId] = new Laya.BatchMark());
        }
        batch(elements) {
            if (!Laya.Config3D.enableDynamicBatch
                || !Laya.LayaGL.renderEngine.getCapable(Laya.RenderCapable.DrawElement_Instance))
                return;
            const elementCount = elements.length;
            const elementArray = elements.elements;
            const maxInstanceCount = WebGLInstanceRenderBatch.MaxInstanceCount;
            elements.length = 0;
            this._updateCountMark++;
            for (let i = 0; i < elementCount; i++) {
                const element = elementArray[i];
                if (element.canDynamicBatch && element.subShader._owner._enableInstancing) {
                    const instanceMark = this.getBatchMark(element);
                    if (this._updateCountMark == instanceMark.updateMark) {
                        const instanceIndex = instanceMark.indexInList;
                        if (instanceMark.batched) {
                            const originElement = elementArray[instanceIndex];
                            const instanceElements = originElement.instanceElementList;
                            if (instanceElements.length === maxInstanceCount) {
                                instanceMark.indexInList = elements.length;
                                instanceMark.batched = false;
                                elements.add(element);
                            }
                            else {
                                instanceElements.add(element);
                            }
                        }
                        else {
                            const originElement = elementArray[instanceIndex];
                            const instanceRenderElement = Laya.Laya3DRender.Render3DPassFactory.createInstanceRenderElement3D();
                            this.recoverList.add(instanceRenderElement);
                            instanceRenderElement.subShader = element.subShader;
                            instanceRenderElement.materialShaderData = element.materialShaderData;
                            instanceRenderElement.materialRenderQueue = element.materialRenderQueue;
                            instanceRenderElement.renderShaderData = element.renderShaderData;
                            instanceRenderElement.owner = element.owner;
                            instanceRenderElement.setGeometry(element.geometry);
                            const list = instanceRenderElement.instanceElementList;
                            list.length = 0;
                            list.add(originElement);
                            list.add(element);
                            elementArray[instanceIndex] = instanceRenderElement;
                            instanceMark.batched = true;
                        }
                    }
                    else {
                        instanceMark.updateMark = this._updateCountMark;
                        instanceMark.indexInList = elements.length;
                        instanceMark.batched = false;
                        elements.add(element);
                    }
                }
                else {
                    elements.add(element);
                }
            }
        }
        clearRenderData() {
            for (let i = this.recoverList.length - 1; i > -1; i--) {
                let element = this.recoverList.elements[i];
                element.clearRenderData();
            }
        }
        recoverData() {
            for (let i = this.recoverList.length - 1; i > -1; i--) {
                let element = this.recoverList.elements[i];
                element.recover();
            }
            this.recoverList.length = 0;
        }
    }
    WebGLInstanceRenderBatch.MaxInstanceCount = 1024;

    class WebGLRenderElement3D {
        constructor() {
            this._shaderInstances = new Laya.FastSinglelist();
        }
        _addShaderInstance(shader) {
            this._shaderInstances.add(shader);
        }
        _clearShaderInstance() {
            this._shaderInstances.length = 0;
        }
        _preUpdatePre(context) {
            this._compileShader(context);
            if (this.materialShaderData && Laya.Config.matUseUBO) {
                let subShader = this.subShader;
                let materialData = this.materialShaderData;
                let matSubBuffer = materialData.createSubUniformBuffer("Material", subShader._owner.name, subShader._uniformMap);
                if (matSubBuffer) {
                    matSubBuffer.upload();
                }
            }
            if (this.owner && Laya.Config._uniformBlock) {
                for (let [key, value] of this.owner.additionShaderData) {
                    let shaderData = value;
                    let unifomrMap = Laya.LayaGL.renderDeviceFactory.createGlobalUniformMap(key);
                    let uniformBuffer = shaderData.createSubUniformBuffer(key, key, unifomrMap._idata);
                    if (uniformBuffer) {
                        uniformBuffer.upload();
                    }
                }
            }
            this._invertFront = this._getInvertFront();
        }
        _getInvertFront() {
            var _a;
            let transform = (_a = this.owner) === null || _a === void 0 ? void 0 : _a.transform;
            return transform ? transform._isFrontFaceInvert : false;
        }
        _render(context) {
            let forceInvertFace = context.invertY;
            let updateMark = context.cameraUpdateMask;
            let sceneShaderData = context.sceneData;
            let cameraShaderData = context.cameraData;
            if (this.isRender) {
                let passes = this._shaderInstances.elements;
                for (let j = 0, m = this._shaderInstances.length; j < m; j++) {
                    const shaderIns = passes[j];
                    if (!shaderIns.complete)
                        continue;
                    let switchShader = shaderIns.bind();
                    let switchUpdateMark = (updateMark !== shaderIns._uploadMark);
                    let uploadScene = (shaderIns._uploadScene !== sceneShaderData) || switchUpdateMark;
                    if (uploadScene || switchShader) {
                        if (sceneShaderData) {
                            shaderIns.uploadUniforms(shaderIns._sceneUniformParamsMap, sceneShaderData, uploadScene);
                        }
                        shaderIns._uploadScene = sceneShaderData;
                    }
                    if (this.renderShaderData) {
                        let uploadSprite3D = (shaderIns._uploadRender !== this.renderShaderData) || switchUpdateMark;
                        if (uploadSprite3D || switchShader) {
                            shaderIns.uploadUniforms(shaderIns._spriteUniformParamsMap, this.renderShaderData, uploadSprite3D);
                            shaderIns._uploadRender = this.renderShaderData;
                        }
                    }
                    if (this.owner) {
                        let additionShaderData = this.owner.additionShaderData;
                        for (let [key, encoder] of shaderIns._additionUniformParamsMaps) {
                            let additionData = additionShaderData.get(key);
                            if (additionData) {
                                let needUpload = shaderIns._additionShaderData.get(key) !== additionData || switchUpdateMark;
                                if (needUpload || switchShader) {
                                    shaderIns.uploadUniforms(encoder, additionData, needUpload);
                                    shaderIns._additionShaderData.set(key, additionData);
                                }
                            }
                        }
                    }
                    let uploadCamera = shaderIns._uploadCameraShaderValue !== cameraShaderData || switchUpdateMark;
                    if (uploadCamera || switchShader) {
                        cameraShaderData && shaderIns.uploadUniforms(shaderIns._cameraUniformParamsMap, cameraShaderData, uploadCamera);
                        shaderIns._uploadCameraShaderValue = cameraShaderData;
                    }
                    let uploadMaterial = (shaderIns._uploadMaterial !== this.materialShaderData) || switchUpdateMark;
                    if (uploadMaterial || switchShader) {
                        shaderIns.uploadUniforms(shaderIns._materialUniformParamsMap, this.materialShaderData, uploadMaterial);
                        shaderIns._uploadMaterial = this.materialShaderData;
                    }
                    shaderIns.uploadRenderStateBlendDepth(this.materialShaderData);
                    shaderIns.uploadRenderStateFrontFace(this.materialShaderData, forceInvertFace, this._invertFront);
                    this.drawGeometry(shaderIns);
                }
            }
        }
        _getShaderInstanceDefines(context) {
            let comDef = WebGLRenderElement3D._compileDefine;
            const globalShaderDefines = context._getContextShaderDefines();
            globalShaderDefines.cloneTo(comDef);
            if (this.renderShaderData) {
                comDef.addDefineDatas(this.renderShaderData.getDefineData());
            }
            if (this.materialShaderData) {
                comDef.addDefineDatas(this.materialShaderData._defineDatas);
            }
            if (this.owner) {
                let additionShaderData = this.owner.additionShaderData;
                if (additionShaderData.size > 0) {
                    for (let [key, value] of additionShaderData.entries()) {
                        comDef.addDefineDatas(value.getDefineData());
                    }
                }
            }
            return comDef;
        }
        _compileShader(context) {
            this._clearShaderInstance();
            var passes = this.subShader._passes;
            for (var j = 0, m = passes.length; j < m; j++) {
                let pass = passes[j];
                let passdata = pass.moduleData;
                if (passdata.pipelineMode !== context.pipelineMode)
                    continue;
                if (this.renderShaderData) {
                    passdata.nodeCommonMap = this.owner._commonUniformMap;
                }
                else {
                    passdata.nodeCommonMap = null;
                }
                passdata.additionShaderData = null;
                if (this.owner) {
                    passdata.additionShaderData = this.owner._additionShaderDataKeys;
                }
                let comDef = this._getShaderInstanceDefines(context);
                var shaderIns = pass.withCompile(comDef);
                this._addShaderInstance(shaderIns);
            }
        }
        drawGeometry(shaderIns) {
            Laya.WebGLEngine.instance.getDrawContext().drawGeometryElement(this.geometry);
        }
        destroy() {
            this.geometry = null;
            this._shaderInstances = null;
            this.materialShaderData = null;
            this.renderShaderData = null;
            this.transform = null;
            this.isRender = null;
        }
    }
    WebGLRenderElement3D._compileDefine = new Laya.WebDefineDatas();

    class WebGLInstanceRenderElement3D extends WebGLRenderElement3D {
        static getInstanceBufferState(geometry, renderType, spriteDefine) {
            let stateinfo = WebGLInstanceRenderElement3D._instanceBufferStateMap.get(geometry._id);
            if (!stateinfo) {
                stateinfo = { state: new Laya.WebGLBufferState() };
                let oriBufferState = geometry.bufferState;
                let vertexArray = oriBufferState._vertexBuffers.slice();
                let worldMatVertex = new Laya.WebGLVertexBuffer(Laya.BufferTargetType.ARRAY_BUFFER, Laya.BufferUsage.Dynamic);
                worldMatVertex.setDataLength(WebGLInstanceRenderElement3D.MaxInstanceCount * 20 * 4);
                worldMatVertex.vertexDeclaration = Laya.VertexMesh.instanceWorldMatrixDeclaration;
                worldMatVertex.instanceBuffer = true;
                vertexArray.push(worldMatVertex);
                stateinfo.worldInstanceVB = worldMatVertex;
                switch (renderType) {
                    case Laya.BaseRenderType.MeshRender:
                        if (spriteDefine.has(Laya.MeshSprite3DShaderDeclaration.SHADERDEFINE_UV1)) {
                            let instanceLightMapVertexBuffer = new Laya.WebGLVertexBuffer(Laya.BufferTargetType.ARRAY_BUFFER, Laya.BufferUsage.Dynamic);
                            instanceLightMapVertexBuffer.setDataLength(WebGLInstanceRenderElement3D.MaxInstanceCount * 4 * 4);
                            instanceLightMapVertexBuffer.vertexDeclaration = Laya.VertexMesh.instanceLightMapScaleOffsetDeclaration;
                            instanceLightMapVertexBuffer.instanceBuffer = true;
                            vertexArray.push(instanceLightMapVertexBuffer);
                            stateinfo.lightmapScaleOffsetVB = instanceLightMapVertexBuffer;
                        }
                        break;
                    case Laya.BaseRenderType.SimpleSkinRender:
                        let instanceSimpleAnimatorBuffer = new Laya.WebGLVertexBuffer(Laya.BufferTargetType.ARRAY_BUFFER, Laya.BufferUsage.Dynamic);
                        instanceSimpleAnimatorBuffer.setDataLength(WebGLInstanceRenderElement3D.MaxInstanceCount * 4 * 4);
                        instanceSimpleAnimatorBuffer.vertexDeclaration = Laya.VertexMesh.instanceSimpleAnimatorDeclaration;
                        instanceSimpleAnimatorBuffer.instanceBuffer = true;
                        vertexArray.push(instanceSimpleAnimatorBuffer);
                        stateinfo.simpleAnimatorVB = instanceSimpleAnimatorBuffer;
                        break;
                }
                stateinfo.state.applyState(vertexArray, geometry.bufferState._bindedIndexBuffer);
                WebGLInstanceRenderElement3D._instanceBufferStateMap.set(geometry._id, stateinfo);
            }
            return stateinfo;
        }
        static create() {
            let element = this._pool.pop() || new WebGLInstanceRenderElement3D();
            return element;
        }
        static _instanceBufferCreate(length) {
            let array = WebGLInstanceRenderElement3D._bufferPool.get(length);
            if (!array) {
                WebGLInstanceRenderElement3D._bufferPool.set(length, []);
                array = WebGLInstanceRenderElement3D._bufferPool.get(length);
            }
            let element = array.pop() || new Float32Array(length);
            return element;
        }
        constructor() {
            super();
            this._vertexBuffers = [];
            this._updateData = [];
            this._updateDataNum = [];
            this.instanceElementList = new Laya.FastSinglelist();
            this.drawCount = 0;
            this.updateNums = 0;
            this.isRender = true;
        }
        addUpdateData(vb, elementLength, maxInstanceCount) {
            this._vertexBuffers[this.updateNums] = vb;
            this._updateDataNum[this.updateNums] = elementLength;
            let data = this._updateData[this.updateNums] = WebGLInstanceRenderElement3D._instanceBufferCreate(elementLength * maxInstanceCount);
            this.updateNums++;
            return data;
        }
        _compileShader(context) {
            this._clearShaderInstance();
            let passes = this.subShader._passes;
            for (let i = 0; i < passes.length; i++) {
                let pass = passes[i];
                if (pass.pipelineMode != context.pipelineMode)
                    continue;
                if (this.renderShaderData) {
                    pass.nodeCommonMap = this.owner._commonUniformMap;
                }
                else {
                    pass.nodeCommonMap = null;
                }
                pass.additionShaderData = null;
                if (this.owner) {
                    pass.additionShaderData = this.owner._additionShaderDataKeys;
                }
                let comDef = this._getShaderInstanceDefines(context);
                comDef.add(Laya.MeshSprite3DShaderDeclaration.SHADERDEFINE_GPU_INSTANCE);
                let shaderIns = pass.withCompile(comDef);
                this._addShaderInstance(shaderIns);
            }
            this._shaderInstances.length > 0 && this._updateInstanceData();
        }
        _updateInstanceData() {
            switch (this.owner.renderNodeType) {
                case Laya.BaseRenderType.MeshRender: {
                    let worldMatrixData = this.addUpdateData(this._instanceStateInfo.worldInstanceVB, 20, WebGLInstanceRenderElement3D.MaxInstanceCount);
                    var insBatches = this.instanceElementList;
                    var elements = insBatches.elements;
                    var count = insBatches.length;
                    this.drawCount = count;
                    this.geometry.instanceCount = this.drawCount;
                    for (var i = 0; i < count; i++) {
                        worldMatrixData.set(elements[i].transform.worldMatrix.elements, i * 20);
                        elements[i].owner._worldParams.writeTo(worldMatrixData, i * 20 + 16);
                    }
                    let haveLightMap = this.renderShaderData.hasDefine(Laya.RenderableSprite3D.SAHDERDEFINE_LIGHTMAP) && this.renderShaderData.hasDefine(Laya.MeshSprite3DShaderDeclaration.SHADERDEFINE_UV1);
                    if (haveLightMap) {
                        let lightMapData = this.addUpdateData(this._instanceStateInfo.lightmapScaleOffsetVB, 4, WebGLInstanceRenderElement3D.MaxInstanceCount);
                        for (var i = 0; i < count; i++) {
                            let lightmapScaleOffset = elements[i].owner.lightmapScaleOffset;
                            var offset = i * 4;
                            lightMapData[offset] = lightmapScaleOffset.x;
                            lightMapData[offset + 1] = lightmapScaleOffset.y;
                            lightMapData[offset + 2] = lightmapScaleOffset.z;
                            lightMapData[offset + 3] = lightmapScaleOffset.w;
                        }
                    }
                    break;
                }
                case Laya.BaseRenderType.SimpleSkinRender: {
                    let worldMatrixData = this.addUpdateData(this._instanceStateInfo.worldInstanceVB, 20, WebGLInstanceRenderElement3D.MaxInstanceCount);
                    var insBatches = this.instanceElementList;
                    var elements = insBatches.elements;
                    var count = insBatches.length;
                    this.drawCount = count;
                    this.geometry.instanceCount = this.drawCount;
                    for (var i = 0; i < count; i++) {
                        worldMatrixData.set(elements[i].transform.worldMatrix.elements, i * 20);
                        elements[i].owner._worldParams.writeTo(worldMatrixData, i * 20 + 16);
                    }
                    let simpleAnimatorData = this.addUpdateData(this._instanceStateInfo.simpleAnimatorVB, 4, WebGLInstanceRenderElement3D.MaxInstanceCount);
                    for (var i = 0; i < count; i++) {
                        var simpleAnimatorParams = elements[i].renderShaderData.getVector(Laya.SimpleSkinnedMeshSprite3D.SIMPLE_SIMPLEANIMATORPARAMS);
                        var offset = i * 4;
                        simpleAnimatorData[offset] = simpleAnimatorParams.x;
                        simpleAnimatorData[offset + 1] = simpleAnimatorParams.y;
                        simpleAnimatorData[offset + 2] = simpleAnimatorParams.z;
                        simpleAnimatorData[offset + 3] = simpleAnimatorParams.w;
                    }
                    break;
                }
            }
        }
        setGeometry(geometry) {
            if (!this.geometry) {
                this.geometry = new Laya.WebGLRenderGeometryElement(geometry.mode, geometry.drawType);
            }
            geometry.cloneTo(this.geometry);
            this.geometry.drawType = Laya.DrawType.DrawElementInstance;
            this._instanceStateInfo = WebGLInstanceRenderElement3D.getInstanceBufferState(geometry, this.owner.renderNodeType, this.renderShaderData._defineDatas);
            this.geometry.bufferState = this._instanceStateInfo.state;
        }
        _render(context) {
            for (let i = 0; i < this.updateNums; i++) {
                let buffer = this._vertexBuffers[i];
                if (!buffer)
                    break;
                let data = this._updateData[i];
                buffer.orphanStorage();
                buffer.setData(data.buffer, 0, 0, this.drawCount * this._updateDataNum[i] * 4);
            }
            super._render(context);
            this.clearRenderData();
        }
        clearRenderData() {
            this.drawCount = 0;
            this.updateNums = 0;
            this._vertexBuffers.length = 0;
            this._updateData.forEach((data) => {
                WebGLInstanceRenderElement3D._bufferPool.get(data.length).push(data);
            });
            this._updateData.length = 0;
            this._updateDataNum.length = 0;
        }
        recover() {
            WebGLInstanceRenderElement3D._pool.push(this);
            this.instanceElementList.clear();
        }
        destroy() {
            super.destroy();
        }
    }
    WebGLInstanceRenderElement3D._instanceBufferStateMap = new Map();
    WebGLInstanceRenderElement3D.MaxInstanceCount = 1024;
    WebGLInstanceRenderElement3D._pool = [];
    WebGLInstanceRenderElement3D._bufferPool = new Map();

    class WebGLDirectLightShadowRP {
        get shadowCasterCommanBuffer() {
            return this._shadowCasterCommanBuffer;
        }
        set shadowCasterCommanBuffer(value) {
            this._shadowCasterCommanBuffer = value;
        }
        set light(value) {
            this._light = value;
            var lightWorld = Laya.Matrix4x4.TEMP;
            var lightWorldE = lightWorld.elements;
            var lightUp = this._lightup;
            var lightSide = this._lightSide;
            var lightForward = this._lightForward;
            Laya.Matrix4x4.createFromQuaternion(this._light.transform.rotation, lightWorld);
            lightSide.setValue(lightWorldE[0], lightWorldE[1], lightWorldE[2]);
            lightUp.setValue(lightWorldE[4], lightWorldE[5], lightWorldE[6]);
            lightForward.setValue(-lightWorldE[8], -lightWorldE[9], -lightWorldE[10]);
            var atlasResolution = this._light.shadowResolution;
            var cascadesMode = this.shadowCastMode = this._light.shadowCascadesMode;
            if (cascadesMode == Laya.ShadowCascadesMode.NoCascades) {
                this._cascadeCount = 1;
                this._shadowTileResolution = atlasResolution;
                this._shadowMapWidth = atlasResolution;
                this._shadowMapHeight = atlasResolution;
            }
            else {
                this._cascadeCount = cascadesMode == Laya.ShadowCascadesMode.TwoCascades ? 2 : 4;
                let shadowTileResolution = Laya.ShadowUtils.getMaxTileResolutionInAtlas(atlasResolution, atlasResolution, this._cascadeCount);
                this._shadowTileResolution = shadowTileResolution;
                this._shadowMapWidth = shadowTileResolution * 2;
                this._shadowMapHeight = cascadesMode == Laya.ShadowCascadesMode.TwoCascades ? shadowTileResolution : shadowTileResolution * 2;
            }
        }
        get light() {
            return this._light;
        }
        constructor() {
            this._cascadesSplitDistance = new Array(WebGLDirectLightShadowRP._maxCascades + 1);
            this._shadowMatrices = new Float32Array(16 * (WebGLDirectLightShadowRP._maxCascades));
            this._splitBoundSpheres = new Float32Array(WebGLDirectLightShadowRP._maxCascades * 4);
            this._shadowSliceDatas = [new Laya.ShadowSliceData(), new Laya.ShadowSliceData(), new Laya.ShadowSliceData(), new Laya.ShadowSliceData()];
            this._shadowMapSize = new Laya.Vector4();
            this._shadowBias = new Laya.Vector4();
            this._cascadeCount = 0;
            this._shadowMapWidth = 0;
            this._shadowMapHeight = 0;
            this._shadowTileResolution = 0;
            this._lightup = new Laya.Vector3();
            this._lightSide = new Laya.Vector3();
            this._lightForward = new Laya.Vector3();
            this._cascadesSplitDistance = new Array(WebGLDirectLightShadowRP._maxCascades + 1);
            this._renderQueue = new RenderListQueue(false);
            this._frustumPlanes = new Array(new Laya.Plane(new Laya.Vector3(), 0), new Laya.Plane(new Laya.Vector3(), 0), new Laya.Plane(new Laya.Vector3(), 0), new Laya.Plane(new Laya.Vector3(), 0), new Laya.Plane(new Laya.Vector3(), 0), new Laya.Plane(new Laya.Vector3(), 0));
            this._shadowCullInfo = new Laya.ShadowCullInfo();
        }
        update(context) {
            var splitDistance = this._cascadesSplitDistance;
            var frustumPlanes = this._frustumPlanes;
            var cameraNear = this.camera.nearplane;
            var shadowFar = Math.min(this.camera.farplane, this._light.shadowDistance);
            var shadowMatrices = this._shadowMatrices;
            var boundSpheres = this._splitBoundSpheres;
            Laya.ShadowUtils.getCascadesSplitDistance(this._light.shadowTwoCascadeSplits, this._light._shadowFourCascadeSplits, cameraNear, shadowFar, this.camera.fieldOfView * Laya.MathUtils3D.Deg2Rad, this.camera.aspectRatio, this.shadowCastMode, splitDistance);
            Laya.ShadowUtils.getCameraFrustumPlanes(this.camera._projectViewMatrix, frustumPlanes);
            var forward = Laya.Vector3.TEMP;
            this.camera.transform.getForward(forward);
            Laya.Vector3.normalize(forward, forward);
            for (var i = 0; i < this._cascadeCount; i++) {
                var sliceData = this._shadowSliceDatas[i];
                sliceData.sphereCenterZ = Laya.ShadowUtils.getBoundSphereByFrustum(splitDistance[i], splitDistance[i + 1], this.camera.fieldOfView * Laya.MathUtils3D.Deg2Rad, this.camera.aspectRatio, this.camera.transform.position, forward, sliceData.splitBoundSphere);
                Laya.ShadowUtils.getDirectionLightShadowCullPlanes(frustumPlanes, i, splitDistance, cameraNear, this._lightForward, sliceData);
                Laya.ShadowUtils.getDirectionalLightMatrices(this._lightup, this._lightSide, this._lightForward, i, this._light.shadowNearPlane, this._shadowTileResolution, sliceData, shadowMatrices);
                if (this._cascadeCount > 1)
                    Laya.ShadowUtils.applySliceTransform(sliceData, this._shadowMapWidth, this._shadowMapHeight, i, shadowMatrices);
            }
            Laya.ShadowUtils.prepareShadowReceiverShaderValues(this._shadowMapWidth, this._shadowMapHeight, this._shadowSliceDatas, this._cascadeCount, this._shadowMapSize, shadowMatrices, boundSpheres);
        }
        render(context, list, count) {
            let shaderValues = context.sceneData;
            context.pipelineMode = "ShadowCaster";
            var shadowMap = this.destTarget;
            context.setRenderTarget(shadowMap, Laya.RenderClearFlag.Depth);
            context.setClearData(Laya.RenderClearFlag.Depth, Laya.Color.BLACK, 1, 0);
            let originCameraData = context.cameraData;
            let originInvertY = context.invertY;
            for (var i = 0, n = this._cascadeCount; i < n; i++) {
                var sliceData = this._shadowSliceDatas[i];
                this.getShadowBias(sliceData.projectionMatrix, sliceData.resolution, this._shadowBias);
                this._setupShadowCasterShaderValues(shaderValues, sliceData, this._lightForward, this._shadowBias);
                var shadowCullInfo = this._shadowCullInfo;
                shadowCullInfo.position = sliceData.position;
                shadowCullInfo.cullPlanes = sliceData.cullPlanes;
                shadowCullInfo.cullPlaneCount = sliceData.cullPlaneCount;
                shadowCullInfo.cullSphere = sliceData.splitBoundSphere;
                shadowCullInfo.direction = this._lightForward;
                var time = performance.now();
                RenderCullUtil.cullDirectLightShadow(shadowCullInfo, list, count, this._renderQueue, context);
                Laya.LayaGL.statAgent.recordTimeData(Laya.StatElement.T_CullShadow, performance.now() - time);
                context.cameraData = sliceData.cameraShaderValue;
                context.invertY = false;
                context.cameraUpdateMask++;
                var resolution = sliceData.resolution;
                var offsetX = sliceData.offsetX;
                var offsetY = sliceData.offsetY;
                if (this._renderQueue.elements.length > 0) {
                    Laya.Viewport.TEMP.set(offsetX, offsetY, resolution, resolution);
                    Laya.Vector4.TEMP.setValue(offsetX + 1, offsetY + 1, resolution - 2, resolution - 2);
                    context.setViewPort(Laya.Viewport.TEMP);
                    context.setScissor(Laya.Vector4.TEMP);
                }
                else {
                    Laya.Viewport.TEMP.set(offsetX, offsetY, resolution, resolution);
                    context.setViewPort(Laya.Viewport.TEMP);
                    Laya.Vector4.TEMP.setValue(offsetX, offsetY, resolution, resolution);
                    context.setScissor(Laya.Vector4.TEMP);
                }
                context.setClearData(Laya.RenderClearFlag.Depth, Laya.Color.BLACK, 1, 0);
                this._renderQueue.renderQueue(context);
                Laya.LayaGL.statAgent.recordCTData(Laya.StatElement.CT_ShadowDrawCall, this._renderQueue.elements.length);
                this._applyCasterPassCommandBuffer(context);
            }
            this._applyRenderData(context.sceneData, context.cameraData);
            this._renderQueue._batch.recoverData();
            context.cameraData = originCameraData;
            context.invertY = originInvertY;
            context.cameraUpdateMask++;
        }
        _applyRenderData(scene, camera) {
            var light = this._light;
            if (light.shadowCascadesMode !== Laya.ShadowCascadesMode.NoCascades)
                scene.addDefine(Laya.Scene3DShaderDeclaration.SHADERDEFINE_SHADOW_CASCADE);
            else
                scene.removeDefine(Laya.Scene3DShaderDeclaration.SHADERDEFINE_SHADOW_CASCADE);
            switch (light.shadowMode) {
                case Laya.ShadowMode.Hard:
                    scene.removeDefine(Laya.Scene3DShaderDeclaration.SHADERDEFINE_SHADOW_SOFT_SHADOW_LOW);
                    scene.removeDefine(Laya.Scene3DShaderDeclaration.SHADERDEFINE_SHADOW_SOFT_SHADOW_HIGH);
                    break;
                case Laya.ShadowMode.SoftLow:
                    scene.addDefine(Laya.Scene3DShaderDeclaration.SHADERDEFINE_SHADOW_SOFT_SHADOW_LOW);
                    scene.removeDefine(Laya.Scene3DShaderDeclaration.SHADERDEFINE_SHADOW_SOFT_SHADOW_HIGH);
                    break;
                case Laya.ShadowMode.SoftHigh:
                    scene.addDefine(Laya.Scene3DShaderDeclaration.SHADERDEFINE_SHADOW_SOFT_SHADOW_HIGH);
                    scene.removeDefine(Laya.Scene3DShaderDeclaration.SHADERDEFINE_SHADOW_SOFT_SHADOW_LOW);
                    break;
            }
            scene.setBuffer(Laya.ShadowCasterPass.SHADOW_MATRICES, this._shadowMatrices);
            scene.setVector(Laya.ShadowCasterPass.SHADOW_MAP_SIZE, this._shadowMapSize);
            scene.setBuffer(Laya.ShadowCasterPass.SHADOW_SPLIT_SPHERES, this._splitBoundSpheres);
        }
        _applyCasterPassCommandBuffer(context) {
            if (!this.shadowCasterCommanBuffer || this.shadowCasterCommanBuffer.length == 0)
                return;
            this.shadowCasterCommanBuffer.forEach(function (value) {
                value._apply();
            });
        }
        getShadowBias(shadowProjectionMatrix, shadowResolution, out) {
            var frustumSize;
            frustumSize = 2.0 / shadowProjectionMatrix.elements[0];
            var texelSize = frustumSize / shadowResolution;
            var depthBias = -this._light.shadowDepthBias * texelSize;
            var normalBias = -this._light.shadowNormalBias * texelSize;
            if (this._light.shadowMode == Laya.ShadowMode.SoftHigh) {
                const kernelRadius = 2.5;
                depthBias *= kernelRadius;
                normalBias *= kernelRadius;
            }
            out.setValue(depthBias, normalBias, 0.0, 0.0);
        }
        _setupShadowCasterShaderValues(shaderValues, shadowSliceData, LightParam, shadowBias) {
            shaderValues.setVector(Laya.ShadowCasterPass.SHADOW_BIAS, shadowBias);
            shaderValues.setVector3(Laya.ShadowCasterPass.SHADOW_LIGHT_DIRECTION, LightParam);
            var cameraSV = shadowSliceData.cameraShaderValue;
            cameraSV.setMatrix4x4(Laya.BaseCamera.VIEWMATRIX, shadowSliceData.viewMatrix);
            cameraSV.setMatrix4x4(Laya.BaseCamera.PROJECTMATRIX, shadowSliceData.projectionMatrix);
            cameraSV.setMatrix4x4(Laya.BaseCamera.VIEWPROJECTMATRIX, shadowSliceData.viewProjectMatrix);
            shaderValues.setMatrix4x4(Laya.BaseCamera.VIEWPROJECTMATRIX, shadowSliceData.viewProjectMatrix);
        }
        destroy() {
            for (var i = 0; i < this._shadowSliceDatas.length; i++) {
                this._shadowSliceDatas[i].destroy();
            }
            this._renderQueue.destroy();
            this._cascadesSplitDistance = null;
            this._frustumPlanes = null;
            this._shadowMatrices = null;
            this._splitBoundSpheres = null;
        }
    }
    WebGLDirectLightShadowRP._maxCascades = 4;

    class WebGLRenderContext3D {
        get sceneData() {
            return this._sceneData;
        }
        set sceneData(value) {
            this._sceneData = value;
            if (Laya.Config._uniformBlock && this.sceneData) {
                for (let key of this._preDrawUniformMaps) {
                    let uniformMap = Laya.LayaGL.renderDeviceFactory.createGlobalUniformMap(key);
                    if (uniformMap._idata.size > 0) {
                        this.sceneData.createUniformBuffer(key, uniformMap._idata);
                    }
                }
            }
        }
        get cameraData() {
            return this._cameraData;
        }
        set cameraData(value) {
            this._cameraData = value;
            if (Laya.Config._uniformBlock && this.cameraData) {
                let cameraMap = Laya.LayaGL.renderDeviceFactory.createGlobalUniformMap("BaseCamera");
                this.cameraData.createUniformBuffer("BaseCamera", cameraMap._idata);
            }
        }
        get sceneModuleData() {
            return this._sceneModuleData;
        }
        set sceneModuleData(value) {
            this._sceneModuleData = value;
        }
        get cameraModuleData() {
            return this._cameraModuleData;
        }
        set cameraModuleData(value) {
            this._cameraModuleData = value;
        }
        get globalShaderData() {
            return this._globalShaderData;
        }
        set globalShaderData(value) {
            this._globalShaderData = value;
        }
        _getContextShaderDefines() {
            return this._cacheGlobalDefines;
        }
        _prepareContext() {
            let contextDef = this._cacheGlobalDefines;
            if (this.sceneData) {
                this.sceneData._defineDatas.cloneTo(contextDef);
                for (let key of this._preDrawUniformMaps) {
                    this.sceneData.updateUBOBuffer(key);
                }
            }
            else {
                this._globalConfigShaderData.cloneTo(contextDef);
            }
            if (this.cameraData) {
                contextDef.addDefineDatas(this.cameraData._defineDatas);
                this.cameraData.updateUBOBuffer("BaseCamera");
            }
        }
        setRenderTarget(value, clearFlag) {
            this._clearFlag = clearFlag;
            if (value == this._renderTarget)
                return;
            this._renderTarget = value;
            this._needStart = true;
        }
        setViewPort(value) {
            this._viewPort = value;
            this._needStart = true;
        }
        setScissor(value) {
            this._scissor = value;
            this._needStart = true;
        }
        get sceneUpdataMask() {
            return this._sceneUpdataMask;
        }
        set sceneUpdataMask(value) {
            this._sceneUpdataMask = value;
        }
        get cameraUpdateMask() {
            return this._cameraUpdateMask;
        }
        set cameraUpdateMask(value) {
            this._cameraUpdateMask = value;
        }
        get pipelineMode() {
            return this._pipelineMode;
        }
        set pipelineMode(value) {
            this._pipelineMode = value;
        }
        get invertY() {
            return this._invertY;
        }
        set invertY(value) {
            this._invertY = value;
        }
        constructor() {
            this._cacheGlobalDefines = new Laya.WebDefineDatas();
            this._needStart = true;
            this._clearColor = new Laya.Color();
            this._globalConfigShaderData = Laya.Shader3D._configDefineValues;
            this._preDrawUniformMaps = new Set();
            this.cameraUpdateMask = 0;
            WebGLRenderContext3D._instance = this;
        }
        runOneCMD(cmd) {
            cmd.apply(this);
        }
        runCMDList(cmds) {
            cmds.forEach(element => {
                element.apply(this);
            });
        }
        setClearData(clearFlag, color, depth, stencil) {
            this._clearFlag = clearFlag;
            color.cloneTo(this._clearColor);
            this._clearDepth = depth;
            this._clearStencil = stencil;
            return 0;
        }
        drawRenderElementList(list) {
            if (this._needStart) {
                this._bindRenderTarget();
                this._start();
                this._needStart = false;
            }
            let time = performance.now();
            this._prepareContext();
            let elements = list.elements;
            for (var i = 0, n = list.length; i < n; i++) {
                elements[i]._preUpdatePre(this);
            }
            let bufferMgr = Laya.WebGLEngine.instance.bufferMgr;
            if (bufferMgr) {
                bufferMgr.upload();
            }
            Laya.LayaGL.statAgent.recordTimeData(Laya.StatElement.T_3DContextPre, performance.now() - time);
            time = performance.now();
            for (var i = 0, n = list.length; i < n; i++) {
                elements[i]._render(this);
            }
            Laya.LayaGL.statAgent.recordTimeData(Laya.StatElement.T_3DContextRender, performance.now() - time);
            Laya.LayaGL.statAgent.recordCTData(Laya.StatElement.CT_3DDrawCall, list.length);
            Laya.LayaGL.renderEngine._framePassCount++;
            return 0;
        }
        drawRenderElementOne(node) {
            if (this._needStart) {
                this._bindRenderTarget();
                this._start();
                this._needStart = false;
            }
            this._prepareContext();
            node._preUpdatePre(this);
            let bufferMgr = Laya.WebGLEngine.instance.bufferMgr;
            if (bufferMgr) {
                bufferMgr.upload();
            }
            node._render(this);
            Laya.LayaGL.statAgent.recordCTData(Laya.StatElement.CT_3DDrawCall, 1);
            Laya.LayaGL.renderEngine._framePassCount++;
            return 0;
        }
        _bindRenderTarget() {
            if (this._renderTarget) {
                Laya.LayaGL.textureContext.bindRenderTarget(this._renderTarget);
            }
            else {
                Laya.LayaGL.textureContext.bindoutScreenTarget();
            }
        }
        _start() {
            Laya.WebGLEngine.instance.scissorTest(true);
            Laya.WebGLEngine.instance.viewport(this._viewPort.x, this._viewPort.y, this._viewPort.width, this._viewPort.height);
            Laya.WebGLEngine.instance.scissor(this._viewPort.x, this._viewPort.y, this._viewPort.width, this._viewPort.height);
            if (this._clearFlag != Laya.RenderClearFlag.Nothing)
                Laya.WebGLEngine.instance.clearRenderTexture(this._clearFlag, this._clearColor, this._clearDepth, this._clearStencil);
            Laya.WebGLEngine.instance.scissor(this._scissor.x, this._scissor.y, this._scissor.z, this._scissor.w);
        }
        clearRenderTarget() {
            this._bindRenderTarget();
            this._start();
        }
    }

    class WebGLForwardAddClusterRP {
        get enableOpaqueTexture() {
            return this._enableOpaqueTexture;
        }
        set enableOpaqueTexture(value) {
            this._enableOpaqueTexture = value;
        }
        setViewPort(value) {
            value.cloneTo(this._viewPort);
        }
        ;
        setScissor(value) {
            value.cloneTo(this._scissor);
        }
        constructor() {
            this.blitOpaqueBuffer = new Laya.CommandBuffer();
            this.opaqueList = new RenderListQueue(false);
            this.transparent = new RenderListQueue(true);
            this.cameraCullInfo = new Laya.CameraCullInfo();
            this._zBufferParams = new Laya.Vector4();
            this._scissor = new Laya.Vector4();
            this._viewPort = new Laya.Viewport();
            this._defaultNormalDepthColor = new Laya.Color(0.5, 0.5, 1.0, 0.0);
            this.clearColor = new Laya.Color();
            this.depthPipelineMode = "ShadowCaster";
            this.depthNormalPipelineMode = "DepthNormal";
            let context = WebGLRenderContext3D._instance;
            context._preDrawUniformMaps.add("Scene3D");
            context._preDrawUniformMaps.add("Shadow");
            context._preDrawUniformMaps.add("Global");
        }
        setCameraCullInfo(value) {
            this.cameraCullInfo.position = value._transform.position;
            this.cameraCullInfo.cullingMask = value.cullingMask;
            this.cameraCullInfo.staticMask = value.staticMask;
            this.cameraCullInfo.boundFrustum = value.boundFrustum;
            this.cameraCullInfo.useOcclusionCulling = value.useOcclusionCulling;
        }
        setBeforeForwardCmds(value) {
            if (value && value.length > 0) {
                this.beforeForwardCmds = value;
                value.forEach(element => {
                    element._apply(false);
                });
            }
        }
        setBeforeSkyboxCmds(value) {
            if (value && value.length > 0) {
                this.beforeSkyboxCmds = value;
                value.forEach(element => {
                    element._apply(false);
                });
            }
        }
        setBeforeTransparentCmds(value) {
            if (value && value.length > 0) {
                this.beforeTransparentCmds = value;
                value.forEach(element => {
                    element._apply(false);
                });
            }
        }
        render(context, list, count) {
            context.cameraUpdateMask++;
            this.opaqueList.clear();
            this.transparent.clear();
            var time = performance.now();
            RenderCullUtil.cullByCameraCullInfo(this.cameraCullInfo, list, count, this.opaqueList, this.transparent, context);
            Laya.LayaGL.statAgent.recordTimeData(Laya.StatElement.T_CullMain, performance.now() - time);
            time = performance.now();
            if ((this.depthTextureMode & Laya.DepthTextureMode.Depth) != 0) {
                this._renderDepthPass(context);
            }
            if ((this.depthTextureMode & Laya.DepthTextureMode.DepthNormals) != 0) {
                this._renderDepthNormalPass(context);
            }
            Laya.LayaGL.statAgent.recordTimeData(Laya.StatElement.T_DepthPass, performance.now() - time);
            this._viewPort.cloneTo(WebGLForwardAddClusterRP._context3DViewPortCatch);
            this._scissor.cloneTo(WebGLForwardAddClusterRP._contextScissorPortCatch);
            time = performance.now();
            this._mainPass(context);
            Laya.LayaGL.statAgent.recordTimeData(Laya.StatElement.T_3DMainPass, performance.now() - time);
            this.opaqueList._batch.recoverData();
        }
        _renderDepthPass(context) {
            context.pipelineMode = this.depthPipelineMode;
            var viewport = this._viewPort;
            var shadervalue = context.sceneData;
            shadervalue.addDefine(Laya.DepthPass.DEPTHPASS);
            shadervalue.setVector(Laya.DepthPass.DEFINE_SHADOW_BIAS, Laya.Vector4.ZERO);
            Laya.Viewport.TEMP.set(viewport.x, viewport.y, viewport.width, viewport.height);
            Laya.Vector4.TEMP.setValue(viewport.x, viewport.y, viewport.width, viewport.height);
            context.setViewPort(Laya.Viewport.TEMP);
            context.setScissor(Laya.Vector4.TEMP);
            context.setRenderTarget(this.depthTarget, Laya.RenderClearFlag.Depth);
            context.setClearData(Laya.RenderClearFlag.Depth, Laya.Color.BLACK, 1, 0);
            this.opaqueList.renderQueue(context);
            Laya.LayaGL.statAgent.recordCTData(Laya.StatElement.CT_DepthCastDrawCall, this.opaqueList.elements.length);
            var far = this.camera.farplane;
            var near = this.camera.nearplane;
            this._zBufferParams.setValue(1.0 - far / near, far / near, (near - far) / (near * far), 1 / near);
            context.cameraData.setVector(Laya.DepthPass.DEFINE_SHADOW_BIAS, Laya.DepthPass.SHADOW_BIAS);
            context.cameraData.setVector(Laya.DepthPass.DEPTHZBUFFERPARAMS, this._zBufferParams);
            shadervalue.removeDefine(Laya.DepthPass.DEPTHPASS);
        }
        _transparentListRender(context) {
            this.transparent.renderQueue(context);
        }
        _opaqueListRender(context) {
            this.opaqueList.renderQueue(context);
        }
        _renderDepthNormalPass(context) {
            context.pipelineMode = this.depthNormalPipelineMode;
            var viewport = this._viewPort;
            Laya.Viewport.TEMP.set(viewport.x, viewport.y, viewport.width, viewport.height);
            Laya.Vector4.TEMP.setValue(viewport.x, viewport.y, viewport.width, viewport.height);
            context.setViewPort(Laya.Viewport.TEMP);
            context.setScissor(Laya.Vector4.TEMP);
            context.setClearData(Laya.RenderClearFlag.Color | Laya.RenderClearFlag.Depth, this._defaultNormalDepthColor, 1, 0);
            context.setRenderTarget(this.depthNormalTarget, Laya.RenderClearFlag.Color | Laya.RenderClearFlag.Depth);
            this.opaqueList.renderQueue(context);
            Laya.LayaGL.statAgent.recordCTData(Laya.StatElement.CT_DepthCastDrawCall, this.opaqueList.elements.length);
        }
        opaqueTexturePass(context) {
            let commanbuffer = this.blitOpaqueBuffer;
            commanbuffer._apply(false);
            context.runCMDList(commanbuffer._renderCMDs);
        }
        _mainPass(context) {
            context.pipelineMode = this.pipelineMode;
            this._rendercmd(this.beforeForwardCmds, context);
            this._recoverRenderContext3D(context);
            context.setClearData(this.clearFlag, this.clearColor, 1, 0);
            var time = performance.now();
            this.enableOpaque && this._opaqueListRender(context);
            Laya.LayaGL.statAgent.recordTimeData(Laya.StatElement.T_3DMainPass_Opaque, performance.now() - time);
            this._rendercmd(this.beforeSkyboxCmds, context);
            if (this.skyRenderNode) {
                let skyRenderNode = this.skyRenderNode;
                let skyRenderElement = skyRenderNode.renderelements[0];
                context.drawRenderElementOne(skyRenderElement);
            }
            if (this.enableOpaque) {
                this.opaqueTexturePass(context);
            }
            this._rendercmd(this.beforeTransparentCmds, context);
            this._recoverRenderContext3D(context);
            time = performance.now();
            this.transparent && this._transparentListRender(context);
            Laya.LayaGL.statAgent.recordTimeData(Laya.StatElement.T_3DMainPass_Trans, performance.now() - time);
        }
        _rendercmd(cmds, context) {
            if (!cmds || cmds.length == 0)
                return;
            cmds.forEach(function (value) {
                context.runCMDList(value._renderCMDs);
            });
        }
        _recoverRenderContext3D(context) {
            const cacheViewPor = WebGLForwardAddClusterRP._context3DViewPortCatch;
            const cacheScissor = WebGLForwardAddClusterRP._contextScissorPortCatch;
            context.setViewPort(cacheViewPor);
            context.setScissor(cacheScissor);
            context.setRenderTarget(this.destTarget, Laya.RenderClearFlag.Nothing);
        }
        destroy() {
            this.cameraCullInfo = null;
            this.beforeForwardCmds = null;
            this.beforeSkyboxCmds = null;
            this.beforeTransparentCmds = null;
            this.blitOpaqueBuffer.clear();
            this.blitOpaqueBuffer = null;
            this.opaqueList.destroy();
            this.transparent.destroy();
        }
    }
    WebGLForwardAddClusterRP._context3DViewPortCatch = new Laya.Viewport(0, 0, 0, 0);
    WebGLForwardAddClusterRP._contextScissorPortCatch = new Laya.Vector4(0, 0, 0, 0);

    class WebGLSpotLightShadowRP {
        set light(value) {
            this._light = value;
            this._shadowResolution = this._light.shadowResolution;
            this._lightWorldMatrix = this._light.getWorldMatrix(this._lightWorldMatrix);
            this._lightPos = this._light.transform.position;
            this._spotAngle = this._light.spotAngle;
            this._spotRange = this._light.spotRange;
        }
        get light() {
            return this._light;
        }
        constructor() {
            this._shadowSpotMapSize = new Laya.Vector4();
            this._shadowSpotMatrices = new Laya.Matrix4x4();
            this._renderQueue = new RenderListQueue(false);
            this._shadowSpotData = new Laya.ShadowSpotData();
            this._lightWorldMatrix = new Laya.Matrix4x4();
            this._shadowBias = new Laya.Vector4();
        }
        update(context) {
            var shadowSpotData = this._shadowSpotData;
            this._getSpotLightShadowData(shadowSpotData, this._shadowResolution, this._shadowSpotMatrices, this._shadowSpotMapSize);
        }
        render(context, list, count) {
            let originCameraData = context.cameraData;
            var shaderValues = context.sceneData;
            context.pipelineMode = "ShadowCaster";
            context.setRenderTarget(this.destTarget, Laya.RenderClearFlag.Depth);
            var shadowSpotData = this._shadowSpotData;
            this._getShadowBias(shadowSpotData.resolution, this._shadowBias);
            this._setupShadowCasterShaderValues(shaderValues, shadowSpotData, this._shadowBias);
            var time = performance.now();
            RenderCullUtil.cullSpotShadow(shadowSpotData.cameraCullInfo, list, count, this._renderQueue, context);
            Laya.LayaGL.statAgent.recordTimeData(Laya.StatElement.T_CullShadow, performance.now() - time);
            context.cameraData = shadowSpotData.cameraShaderValue;
            context.cameraUpdateMask++;
            Laya.Viewport.TEMP.set(shadowSpotData.offsetX, shadowSpotData.offsetY, shadowSpotData.resolution, shadowSpotData.resolution);
            Laya.Vector4.TEMP.setValue(shadowSpotData.offsetX, shadowSpotData.offsetY, shadowSpotData.resolution, shadowSpotData.resolution);
            context.setViewPort(Laya.Viewport.TEMP);
            context.setScissor(Laya.Vector4.TEMP);
            context.setClearData(Laya.RenderClearFlag.Depth, Laya.Color.BLACK, 1, 0);
            this._renderQueue.renderQueue(context);
            Laya.LayaGL.statAgent.recordCTData(Laya.StatElement.CT_ShadowDrawCall, this._renderQueue.elements.length);
            this._applyCasterPassCommandBuffer(context);
            this._applyRenderData(context.sceneData, context.cameraData);
            this._renderQueue._batch.recoverData();
            context.cameraData = originCameraData;
            context.cameraUpdateMask++;
        }
        _getSpotLightShadowData(shadowSpotData, resolution, shadowSpotMatrices, shadowMapSize) {
            var out = shadowSpotData.position = this._lightPos;
            shadowSpotData.resolution = resolution;
            shadowMapSize.setValue(1.0 / resolution, 1.0 / resolution, resolution, resolution);
            shadowSpotData.offsetX = 0;
            shadowSpotData.offsetY = 0;
            var spotWorldMatrix = this._lightWorldMatrix;
            var viewMatrix = shadowSpotData.viewMatrix;
            var projectMatrix = shadowSpotData.projectionMatrix;
            var viewProjectMatrix = shadowSpotData.viewProjectMatrix;
            var BoundFrustum = shadowSpotData.cameraCullInfo.boundFrustum;
            spotWorldMatrix.invert(viewMatrix);
            Laya.Matrix4x4.createPerspective(3.1416 * this._spotAngle / 180.0, 1, 0.1, this._spotRange, projectMatrix);
            Laya.Matrix4x4.multiply(projectMatrix, viewMatrix, viewProjectMatrix);
            BoundFrustum.matrix = viewProjectMatrix;
            viewProjectMatrix.cloneTo(shadowSpotMatrices);
            shadowSpotData.cameraCullInfo.position = out;
        }
        _getShadowBias(shadowResolution, out) {
            var frustumSize = Math.tan(this._spotAngle * 0.5 * Laya.MathUtils3D.Deg2Rad) * this._spotRange;
            var texelSize = frustumSize / shadowResolution;
            var depthBias = -this._light.shadowDepthBias * texelSize;
            var normalBias = -this._light.shadowNormalBias * texelSize;
            if (this._shadowMode == Laya.ShadowMode.SoftHigh) {
                const kernelRadius = 2.5;
                depthBias *= kernelRadius;
                normalBias *= kernelRadius;
            }
            out.setValue(depthBias, normalBias, 0.0, 0.0);
        }
        _setupShadowCasterShaderValues(shaderValues, shadowSliceData, shadowBias) {
            shaderValues.setVector(Laya.ShadowCasterPass.SHADOW_BIAS, shadowBias);
            var cameraSV = shadowSliceData.cameraShaderValue;
            cameraSV.setMatrix4x4(Laya.BaseCamera.VIEWMATRIX, shadowSliceData.viewMatrix);
            cameraSV.setMatrix4x4(Laya.BaseCamera.PROJECTMATRIX, shadowSliceData.projectionMatrix);
            cameraSV.setMatrix4x4(Laya.BaseCamera.VIEWPROJECTMATRIX, shadowSliceData.viewProjectMatrix);
            shaderValues.setMatrix4x4(Laya.BaseCamera.VIEWPROJECTMATRIX, shadowSliceData.viewProjectMatrix);
        }
        _applyCasterPassCommandBuffer(context) {
            if (!this.shadowCasterCommanBuffer || this.shadowCasterCommanBuffer.length == 0)
                return;
            this.shadowCasterCommanBuffer.forEach(function (value) {
                value._apply();
            });
        }
        _applyRenderData(sceneData, cameraData) {
            var spotLight = this._light;
            switch (spotLight.shadowMode) {
                case Laya.ShadowMode.Hard:
                    sceneData.removeDefine(Laya.Scene3DShaderDeclaration.SHADERDEFINE_SHADOW_SPOT_SOFT_SHADOW_HIGH);
                    sceneData.removeDefine(Laya.Scene3DShaderDeclaration.SHADERDEFINE_SHADOW_SPOT_SOFT_SHADOW_LOW);
                    break;
                case Laya.ShadowMode.SoftLow:
                    sceneData.addDefine(Laya.Scene3DShaderDeclaration.SHADERDEFINE_SHADOW_SPOT_SOFT_SHADOW_LOW);
                    sceneData.removeDefine(Laya.Scene3DShaderDeclaration.SHADERDEFINE_SHADOW_SPOT_SOFT_SHADOW_HIGH);
                    break;
                case Laya.ShadowMode.SoftHigh:
                    sceneData.addDefine(Laya.Scene3DShaderDeclaration.SHADERDEFINE_SHADOW_SPOT_SOFT_SHADOW_HIGH);
                    sceneData.removeDefine(Laya.Scene3DShaderDeclaration.SHADERDEFINE_SHADOW_SPOT_SOFT_SHADOW_LOW);
                    break;
            }
            sceneData.setMatrix4x4(Laya.ShadowCasterPass.SHADOW_SPOTMATRICES, this._shadowSpotMatrices);
            sceneData.setVector(Laya.ShadowCasterPass.SHADOW_SPOTMAP_SIZE, this._shadowSpotMapSize);
        }
        destroy() {
            this._shadowSpotData.destroy();
        }
    }

    class WebGLForwardAddRP {
        constructor() {
            this.shadowCastPass = false;
            this.enableDirectLightShadow = false;
            this.enableSpotLightShadowPass = false;
            this.enablePostProcess = true;
            this.directLightShadowPass = new WebGLDirectLightShadowRP();
            this.spotLightShadowPass = new WebGLSpotLightShadowRP();
            this.shadowParams = new Laya.Vector4();
            this.renderpass = new WebGLForwardAddClusterRP();
            this.finalize = new Laya.CommandBuffer();
        }
        setBeforeImageEffect(value) {
            if (value && value.length > 0) {
                this._beforeImageEffectCMDS = value;
                value.forEach(element => {
                    element._apply(false);
                });
            }
        }
        setAfterEventCmd(value) {
            if (value && value.length > 0) {
                this._afterAllRenderCMDS = value;
                value.forEach(element => {
                    element._apply(false);
                });
            }
        }
        destroy() {
            this._afterAllRenderCMDS = null;
            this._beforeImageEffectCMDS = null;
            this.renderpass.destroy();
            this.directLightShadowPass.destroy();
            this.spotLightShadowPass.destroy();
            this.finalize.clear();
            this.finalize = null;
        }
    }

    const viewport$1 = new Laya.Viewport(0, 0, 0, 0);
    const offsetScale = new Laya.Vector4();
    class WebGLRender3DProcess {
        constructor() {
            this.renderpass = new WebGLForwardAddRP();
        }
        initRenderpass(camera, context) {
            let renderpass = this.renderpass.renderpass;
            let renderRT = camera._getRenderTexture();
            let clearConst = 0;
            let clearFlag = camera.clearFlag;
            if (clearFlag == Laya.CameraClearFlags.Sky && !camera.scene.skyRenderer._isAvailable()) {
                clearFlag = Laya.CameraClearFlags.SolidColor;
            }
            let hasStencil = renderRT.depthStencilFormat == Laya.RenderTargetFormat.DEPTHSTENCIL_24_8;
            let stencilFlag = hasStencil ? Laya.RenderClearFlag.Stencil : 0;
            switch (clearFlag) {
                case Laya.CameraClearFlags.DepthOnly:
                case Laya.CameraClearFlags.Sky:
                    clearConst = Laya.RenderClearFlag.Depth | stencilFlag;
                    break;
                case Laya.CameraClearFlags.Nothing:
                    clearConst = 0;
                    break;
                case Laya.CameraClearFlags.ColorOnly:
                    clearConst = Laya.RenderClearFlag.Color;
                    break;
                case Laya.CameraClearFlags.SolidColor:
                default:
                    clearConst = Laya.RenderClearFlag.Color | Laya.RenderClearFlag.Depth | stencilFlag;
                    break;
            }
            let clearValue = camera._linearClearColor;
            clearValue = renderRT.gammaCorrection != 1 ? camera.clearColor : camera._linearClearColor;
            renderpass.camera = camera._renderDataModule;
            renderpass.destTarget = renderRT._renderTarget;
            renderpass.clearFlag = clearConst;
            renderpass.clearColor = clearValue;
            let needInternalRT = camera._needInternalRenderTexture();
            if (needInternalRT) {
                viewport$1.set(0, 0, renderRT.width, renderRT.height);
            }
            else {
                camera.viewport.cloneTo(viewport$1);
            }
            renderpass.setViewPort(viewport$1);
            let scissor = Laya.Vector4.TEMP;
            scissor.setValue(viewport$1.x, viewport$1.y, viewport$1.width, viewport$1.height);
            renderpass.setScissor(scissor);
            renderpass.enableOpaque = Laya.Stat.enableOpaque;
            renderpass.enableTransparent = Laya.Stat.enableTransparent;
            renderpass.enableCMD = Laya.Stat.enableCameraCMD;
            renderpass.setBeforeSkyboxCmds(camera._cameraEventCommandBuffer[Laya.CameraEventFlags.BeforeSkyBox]);
            renderpass.setBeforeForwardCmds(camera._cameraEventCommandBuffer[Laya.CameraEventFlags.BeforeForwardOpaque]);
            renderpass.setBeforeTransparentCmds(camera._cameraEventCommandBuffer[Laya.CameraEventFlags.BeforeTransparent]);
            this.renderpass.setBeforeImageEffect(camera._cameraEventCommandBuffer[Laya.CameraEventFlags.BeforeImageEffect]);
            this.renderpass.setAfterEventCmd(camera._cameraEventCommandBuffer[Laya.CameraEventFlags.AfterEveryThing]);
            renderpass.setCameraCullInfo(camera);
            if (clearFlag == Laya.CameraClearFlags.Sky) {
                renderpass.skyRenderNode = camera.scene.skyRenderer._baseRenderNode;
            }
            else {
                renderpass.skyRenderNode = null;
            }
            renderpass.pipelineMode = Laya.RenderContext3D._instance.configPipeLineMode;
            let enableShadow = Laya.Scene3D._updateMark % camera.scene._ShadowMapupdateFrequency == 0 && Laya.Stat.enableShadow;
            this.renderpass.shadowCastPass = enableShadow;
            if (enableShadow) {
                let shadowParams = this.renderpass.shadowParams;
                shadowParams.setValue(0, 0, 0, 0);
                let sceneShaderData = context.sceneData;
                let mainDirectionLight = camera.scene._mainDirectionLight;
                let needDirectionShadow = mainDirectionLight && mainDirectionLight.shadowMode != Laya.ShadowMode.None;
                this.renderpass.enableDirectLightShadow = needDirectionShadow;
                if (needDirectionShadow) {
                    this.renderpass.directLightShadowPass.camera = camera._renderDataModule;
                    this.renderpass.directLightShadowPass.light = mainDirectionLight._dataModule;
                    let directionShadowMap = Laya.ILaya.Scene3D._shadowCasterPass.getDirectLightShadowMap(mainDirectionLight);
                    this.renderpass.directLightShadowPass.destTarget = directionShadowMap._renderTarget;
                    shadowParams.x = this.renderpass.directLightShadowPass.light.shadowStrength;
                    sceneShaderData.setTexture(Laya.ShadowCasterPass.SHADOW_MAP, directionShadowMap);
                }
                let mainSpotLight = camera.scene._mainSpotLight;
                let needSpotShadow = mainSpotLight && mainSpotLight.shadowMode != Laya.ShadowMode.None;
                this.renderpass.enableSpotLightShadowPass = needSpotShadow;
                if (needSpotShadow) {
                    this.renderpass.spotLightShadowPass.light = mainSpotLight._dataModule;
                    let spotShadowMap = Laya.ILaya.Scene3D._shadowCasterPass.getSpotLightShadowPassData(mainSpotLight);
                    this.renderpass.spotLightShadowPass.destTarget = spotShadowMap._renderTarget;
                    shadowParams.y = this.renderpass.spotLightShadowPass.light.shadowStrength;
                    sceneShaderData.setTexture(Laya.ShadowCasterPass.SHADOW_SPOTMAP, spotShadowMap);
                }
                sceneShaderData.setVector(Laya.ShadowCasterPass.SHADOW_PARAMS, this.renderpass.shadowParams);
            }
            renderpass.blitOpaqueBuffer.clear();
            let needBlitOpaque = camera.opaquePass;
            renderpass.enableOpaqueTexture = needBlitOpaque;
            if (needBlitOpaque) {
                renderpass.opaqueTexture = camera._opaqueTexture._renderTarget;
                renderpass.blitOpaqueBuffer.blitScreenQuad(renderRT, camera._opaqueTexture);
            }
            if (Laya.Stat.enablePostprocess && camera.postProcess && camera.postProcess.enable && camera.postProcess.effects.length > 0) {
                this.renderpass.enablePostProcess = Laya.Stat.enablePostprocess;
                this.renderpass.postProcess = camera.postProcess._context.command;
                camera.postProcess._render(camera);
                this.renderpass.postProcess._apply(false);
            }
            else {
                this.renderpass.enablePostProcess = false;
            }
            this.renderpass.finalize.clear();
            if (!this.renderpass.enablePostProcess && needInternalRT && camera._offScreenRenderTexture) {
                let dst = camera._offScreenRenderTexture;
                offsetScale.setValue(camera.normalizedViewport.x, 1.0 - camera.normalizedViewport.y, renderRT.width / dst.width, -renderRT.height / dst.height);
                this.renderpass.finalize.blitScreenQuad(renderRT, camera._offScreenRenderTexture, offsetScale);
            }
        }
        renderDepth(camera) {
            let depthMode = camera.depthTextureMode;
            if (camera.postProcess && camera.postProcess.enable) {
                depthMode |= camera.postProcess.cameraDepthTextureMode;
            }
            if ((depthMode & Laya.DepthTextureMode.Depth) != 0) {
                Laya.Camera.depthPass.getTarget(camera, Laya.DepthTextureMode.Depth, camera.depthTextureFormat);
                this.renderpass.renderpass.depthTarget = camera.depthTexture._renderTarget;
                Laya.Camera.depthPass._setupDepthModeShaderValue(Laya.DepthTextureMode.Depth, camera);
            }
            if ((depthMode & Laya.DepthTextureMode.DepthNormals) != 0) {
                Laya.Camera.depthPass.getTarget(camera, Laya.DepthTextureMode.DepthNormals, camera.depthTextureFormat);
                this.renderpass.renderpass.depthNormalTarget = camera.depthNormalTexture._renderTarget;
                camera._shaderValues.setTexture(Laya.DepthPass.DEPTHNORMALSTEXTURE, camera.depthNormalTexture);
                Laya.Camera.depthPass._setupDepthModeShaderValue(Laya.DepthTextureMode.DepthNormals, camera);
            }
            this.renderpass.renderpass.depthTextureMode = depthMode;
        }
        fowardRender(context, camera) {
            Laya.Camera.depthPass.cleanUp(camera);
            this.renderDepth(camera);
            this.initRenderpass(camera, context);
            let renderList = this.render3DManager.baseRenderList.elements;
            let count = this.render3DManager.baseRenderList.length;
            this.renderFowarAddCameraPass(context, this.renderpass, renderList, count);
        }
        renderFowarAddCameraPass(context, renderpass, list, count) {
            var time = performance.now();
            if (renderpass.shadowCastPass) {
                if (renderpass.enableDirectLightShadow) {
                    context.sceneData.addDefine(Laya.Scene3DShaderDeclaration.SHADERDEFINE_SHADOW);
                    context.sceneData.removeDefine(Laya.Scene3DShaderDeclaration.SHADERDEFINE_SHADOW_SPOT);
                    renderpass.directLightShadowPass.update(context);
                    renderpass.directLightShadowPass.render(context, list, count);
                }
                if (renderpass.enableSpotLightShadowPass) {
                    context.sceneData.addDefine(Laya.Scene3DShaderDeclaration.SHADERDEFINE_SHADOW_SPOT);
                    context.sceneData.removeDefine(Laya.Scene3DShaderDeclaration.SHADERDEFINE_SHADOW);
                    renderpass.spotLightShadowPass.update(context);
                    renderpass.spotLightShadowPass.render(context, list, count);
                }
                if (renderpass.enableDirectLightShadow) {
                    context.sceneData.addDefine(Laya.Scene3DShaderDeclaration.SHADERDEFINE_SHADOW);
                }
                else {
                    context.sceneData.removeDefine(Laya.Scene3DShaderDeclaration.SHADERDEFINE_SHADOW);
                }
                if (renderpass.enableSpotLightShadowPass) {
                    context.sceneData.addDefine(Laya.Scene3DShaderDeclaration.SHADERDEFINE_SHADOW_SPOT);
                }
                else {
                    context.sceneData.removeDefine(Laya.Scene3DShaderDeclaration.SHADERDEFINE_SHADOW_SPOT);
                }
            }
            Laya.LayaGL.statAgent.recordTimeData(Laya.StatElement.T_ShadowPass, performance.now() - time);
            renderpass.renderpass.render(context, list, count);
            renderpass._beforeImageEffectCMDS && this._rendercmd(renderpass._beforeImageEffectCMDS, context);
            if (renderpass.enablePostProcess) {
                time = performance.now();
                renderpass.postProcess && this._renderPostProcess(renderpass.postProcess, context);
                Laya.LayaGL.statAgent.recordTimeData(Laya.StatElement.T_Render_PostProcess, performance.now() - time);
            }
            renderpass._afterAllRenderCMDS && this._rendercmd(renderpass._afterAllRenderCMDS, context);
            renderpass.finalize._apply(false);
            context.runCMDList(renderpass.finalize._renderCMDs);
        }
        _rendercmd(cmds, context) {
            if (!cmds || cmds.length == 0)
                return;
            cmds.forEach(function (value) {
                context.runCMDList(value._renderCMDs);
            });
        }
        _renderPostProcess(postprocessCMD, context) {
            context.runCMDList(postprocessCMD._renderCMDs);
        }
        destroy() {
            this.renderpass.destroy();
        }
    }

    class WebGLDrawNodeCMDData extends Laya.DrawNodeCMDData {
        get node() {
            return this._node;
        }
        set node(value) {
            this._node = value;
        }
        get destShaderData() {
            return this._destShaderData;
        }
        set destShaderData(value) {
            this._destShaderData = value;
        }
        get destSubShader() {
            return this._destSubShader;
        }
        set destSubShader(value) {
            this._destSubShader = value;
        }
        get subMeshIndex() {
            return this._subMeshIndex;
        }
        set subMeshIndex(value) {
            this._subMeshIndex = value;
        }
        constructor() {
            super();
            this.type = Laya.RenderCMDType.DrawNode;
        }
        apply(context) {
            if (this.destShaderData && this.destSubShader) {
                this.node._renderUpdatePre(context);
                if (this.subMeshIndex == -1) {
                    this.node.renderelements.forEach(element => {
                        let oriSubShader = element.subShader;
                        let oriMatShaderData = element.materialShaderData;
                        element.subShader = this._destSubShader;
                        element.materialShaderData = this._destShaderData;
                        context.drawRenderElementOne(element);
                        element.subShader = oriSubShader;
                        element.materialShaderData = oriMatShaderData;
                    });
                }
                else {
                    let element = this.node.renderelements[this.subMeshIndex];
                    let oriSubShader = element.subShader;
                    let oriMatShaderData = element.materialShaderData;
                    element.subShader = this._destSubShader;
                    element.materialShaderData = this._destShaderData;
                    context.drawRenderElementOne(element);
                    element.subShader = oriSubShader;
                    element.materialShaderData = oriMatShaderData;
                }
            }
        }
    }
    class WebGLBlitQuadCMDData extends Laya.BlitQuadCMDData {
        get dest() {
            return this._dest;
        }
        set dest(value) {
            this._dest = value;
        }
        get viewport() {
            return this._viewport;
        }
        set viewport(value) {
            value.cloneTo(this._viewport);
        }
        get scissor() {
            return this._scissor;
        }
        set scissor(value) {
            value.cloneTo(this._scissor);
        }
        get source() {
            return this._source;
        }
        set source(value) {
            this._source = value;
            if (this._source) {
                this._sourceTexelSize.setValue(1.0 / this._source.width, 1.0 / this._source.height, this._source.width, this._source.height);
            }
        }
        get offsetScale() {
            return this._offsetScale;
        }
        set offsetScale(value) {
            value.cloneTo(this._offsetScale);
        }
        get element() {
            return this._element;
        }
        set element(value) {
            this._element = value;
        }
        constructor() {
            super();
            this.type = Laya.RenderCMDType.Blit;
            this._viewport = new Laya.Viewport();
            this._scissor = new Laya.Vector4();
            this._offsetScale = new Laya.Vector4();
            this._sourceTexelSize = new Laya.Vector4();
        }
        apply(context) {
            this.element.materialShaderData._setInternalTexture(Laya.Command.SCREENTEXTURE_ID, this._source);
            this.element.materialShaderData.setVector(Laya.Command.SCREENTEXTUREOFFSETSCALE_ID, this._offsetScale);
            this.element.materialShaderData.setVector(Laya.Command.MAINTEXTURE_TEXELSIZE_ID, this._sourceTexelSize);
            context.setViewPort(this._viewport);
            context.setScissor(this._scissor);
            context.setRenderTarget(this.dest, Laya.RenderClearFlag.Nothing);
            context.drawRenderElementOne(this.element);
        }
    }
    class WebGLDrawElementCMDData extends Laya.DrawElementCMDData {
        constructor() {
            super();
            this.type = Laya.RenderCMDType.DrawElement;
        }
        setRenderelements(value) {
            this._elemets = value;
        }
        apply(context) {
            if (this._elemets.length == 1) {
                context.drawRenderElementOne(this._elemets[0]);
            }
            else {
                this._elemets.forEach(element => {
                    context.drawRenderElementOne(element);
                });
            }
        }
    }
    class WebGLSetViewportCMD extends Laya.SetViewportCMD {
        get viewport() {
            return this._viewport;
        }
        set viewport(value) {
            this._viewport = value;
        }
        get scissor() {
            return this._scissor;
        }
        set scissor(value) {
            this._scissor = value;
        }
        constructor() {
            super();
            this.type = Laya.RenderCMDType.ChangeViewPort;
            this.scissor = new Laya.Vector4();
            this.viewport = new Laya.Viewport();
        }
        apply(context) {
            context.setViewPort(this.viewport);
            context.setScissor(this.scissor);
        }
    }
    const viewport = new Laya.Viewport();
    const scissor = new Laya.Vector4();
    class WebGLSetRenderTargetCMD extends Laya.SetRenderTargetCMD {
        get rt() {
            return this._rt;
        }
        set rt(value) {
            this._rt = value;
        }
        get clearFlag() {
            return this._clearFlag;
        }
        set clearFlag(value) {
            this._clearFlag = value;
        }
        get clearColorValue() {
            return this._clearColorValue;
        }
        set clearColorValue(value) {
            value.cloneTo(this._clearColorValue);
        }
        get clearDepthValue() {
            return this._clearDepthValue;
        }
        set clearDepthValue(value) {
            this._clearDepthValue = value;
        }
        get clearStencilValue() {
            return this._clearStencilValue;
        }
        set clearStencilValue(value) {
            this._clearStencilValue = value;
        }
        constructor() {
            super();
            this.type = Laya.RenderCMDType.ChangeRenderTarget;
            this._clearColorValue = new Laya.Color();
        }
        apply(context) {
            context.setRenderTarget(this.rt, Laya.RenderClearFlag.Nothing);
            context.setClearData(this.clearFlag, this.clearColorValue, this.clearDepthValue, this.clearStencilValue);
            if (this.rt) {
                viewport.set(0, 0, this.rt._textures[0].width, this.rt._textures[0].height);
                scissor.setValue(0, 0, this.rt._textures[0].width, this.rt._textures[0].height);
                context.setViewPort(viewport);
                context.setScissor(scissor);
            }
        }
    }

    class WebGLSkinRenderElement3D extends WebGLRenderElement3D {
        constructor() {
            super();
        }
        drawGeometry(shaderIns) {
            let element = this.geometry.drawParams.elements;
            if (!this.skinnedData)
                return;
            this.geometry.bufferState.bind();
            let shaderVariable = shaderIns._cacheShaerVariable[Laya.SkinnedMeshRenderer.BONES];
            if (!shaderVariable) {
                for (var i = 0, n = shaderIns._spriteUniformParamsMap._idata.length; i < n; i++) {
                    if (shaderIns._spriteUniformParamsMap._idata[i].dataOffset == Laya.SkinnedMeshRenderer.BONES) {
                        shaderVariable = shaderIns._spriteUniformParamsMap._idata[i];
                        shaderIns._cacheShaerVariable[Laya.SkinnedMeshRenderer.BONES] = shaderVariable;
                        break;
                    }
                }
            }
            for (var j = 0, m = this.geometry.drawParams.length / 2; j < m; j++) {
                var subSkinnedDatas = this.skinnedData[j];
                Laya.WebGLEngine.instance.uploadOneUniforms(shaderIns._renderShaderInstance, shaderVariable, subSkinnedDatas);
                var offset = j * 2;
                Laya.WebGLEngine.instance.getDrawContext().drawElements(this.geometry._glmode, element[offset + 1], this.geometry._glindexFormat, element[offset]);
            }
        }
    }

    WebBaseRenderNode.BaseRenderNodeClass = WebBaseRenderNode;
    class WebGL3DRenderPassFactory {
        createInstanceBatch() {
            return new WebGLInstanceRenderBatch();
        }
        createSetRenderDataCMD() {
            return new Laya.WebGLSetRenderData();
        }
        createSetShaderDefineCMD() {
            return new Laya.WebGLSetShaderDefine();
        }
        createDrawNodeCMDData() {
            return new WebGLDrawNodeCMDData();
        }
        createBlitQuadCMDData() {
            return new WebGLBlitQuadCMDData();
        }
        createDrawElementCMDData() {
            return new WebGLDrawElementCMDData();
        }
        createSetViewportCMD() {
            return new WebGLSetViewportCMD();
        }
        createSetRenderTargetCMD() {
            return new WebGLSetRenderTargetCMD();
        }
        createSceneRenderManager() {
            return new WebSceneRenderManager();
        }
        createSkinRenderElement() {
            return new WebGLSkinRenderElement3D();
        }
        createRenderContext3D() {
            let context = new WebGLRenderContext3D();
            return context;
        }
        createRenderElement3D() {
            return new WebGLRenderElement3D();
        }
        createInstanceRenderElement3D() {
            return WebGLInstanceRenderElement3D.create();
        }
        createRender3DProcess() {
            return new WebGLRender3DProcess();
        }
    }
    Laya.Laya.addBeforeInitCallback(() => {
        if (!Laya.Laya3DRender.Render3DPassFactory)
            Laya.Laya3DRender.Render3DPassFactory = new WebGL3DRenderPassFactory();
    });

    exports.ForwardAddClusterRP = ForwardAddClusterRP;
    exports.RenderCullUtil = RenderCullUtil;
    exports.RenderListQueue = RenderListQueue;
    exports.RenderPassUtil = RenderPassUtil;
    exports.RenderQuickSort = RenderQuickSort;
    exports.Web3DRenderModuleFactory = Web3DRenderModuleFactory;
    exports.WebBaseRenderNode = WebBaseRenderNode;
    exports.WebCameraNodeData = WebCameraNodeData;
    exports.WebDirectLight = WebDirectLight;
    exports.WebGL3DRenderPassFactory = WebGL3DRenderPassFactory;
    exports.WebGLBlitQuadCMDData = WebGLBlitQuadCMDData;
    exports.WebGLDirectLightShadowRP = WebGLDirectLightShadowRP;
    exports.WebGLDrawElementCMDData = WebGLDrawElementCMDData;
    exports.WebGLDrawNodeCMDData = WebGLDrawNodeCMDData;
    exports.WebGLForwardAddClusterRP = WebGLForwardAddClusterRP;
    exports.WebGLForwardAddRP = WebGLForwardAddRP;
    exports.WebGLInstanceRenderBatch = WebGLInstanceRenderBatch;
    exports.WebGLInstanceRenderElement3D = WebGLInstanceRenderElement3D;
    exports.WebGLRender3DProcess = WebGLRender3DProcess;
    exports.WebGLRenderContext3D = WebGLRenderContext3D;
    exports.WebGLRenderElement3D = WebGLRenderElement3D;
    exports.WebGLSetRenderTargetCMD = WebGLSetRenderTargetCMD;
    exports.WebGLSetViewportCMD = WebGLSetViewportCMD;
    exports.WebGLSkinRenderElement3D = WebGLSkinRenderElement3D;
    exports.WebGLSpotLightShadowRP = WebGLSpotLightShadowRP;
    exports.WebLightmap = WebLightmap;
    exports.WebMeshRenderNode = WebMeshRenderNode;
    exports.WebPointLight = WebPointLight;
    exports.WebReflectionProbe = WebReflectionProbe;
    exports.WebSceneNodeData = WebSceneNodeData;
    exports.WebSceneRenderManager = WebSceneRenderManager;
    exports.WebSimpleSkinRenderNode = WebSimpleSkinRenderNode;
    exports.WebSkinRenderNode = WebSkinRenderNode;
    exports.WebSpotLight = WebSpotLight;
    exports.WebVolumetricGI = WebVolumetricGI;

})(window.Laya = window.Laya || {}, Laya);
