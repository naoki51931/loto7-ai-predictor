package com.naoki51931.loto7aipredictor

import kotlin.math.exp
import kotlin.math.sqrt
import kotlin.random.Random

data class NeuralNetworkSnapshot(val w1:Array<DoubleArray>,val b1:DoubleArray,val w2:Array<DoubleArray>,val b2:DoubleArray,val w3:Array<DoubleArray>,val b3:DoubleArray)

class LotoNeuralNetwork(private val inputSize:Int=37,private val hidden1:Int=256,private val hidden2:Int=128,private val outputSize:Int=37,seed:Int=51931){
 private val random=Random(seed); private val w1=Array(hidden1){DoubleArray(inputSize){init(inputSize)}}; private val b1=DoubleArray(hidden1); private val w2=Array(hidden2){DoubleArray(hidden1){init(hidden1)}}; private val b2=DoubleArray(hidden2); private val w3=Array(outputSize){DoubleArray(hidden2){init(hidden2)}}; private val b3=DoubleArray(outputSize)
 private fun init(f:Int)=(random.nextDouble()*2-1)*sqrt(2.0/f); private fun relu(x:Double)=if(x>0)x else 0.0; private fun sigmoid(x:Double)=1.0/(1.0+exp(-x.coerceIn(-30.0,30.0)))
 fun features(history:List<List<Int>>,window:Int):DoubleArray{val a=history.takeLast(window);val x=DoubleArray(37);if(a.isEmpty())return x;a.forEachIndexed{idx,ns->val r=exp(-(a.size-1-idx)/16.0);ns.forEach{n->if(n in 1..37)x[n-1]+=r}};val m=x.maxOrNull()?.coerceAtLeast(1e-9)?:1.0;for(i in x.indices)x[i]/=m;return x}
 private data class F(val x:DoubleArray,val z1:DoubleArray,val h1:DoubleArray,val z2:DoubleArray,val h2:DoubleArray,val y:DoubleArray)
 private fun forward(x:DoubleArray):F{val z1=DoubleArray(hidden1){j->b1[j]+w1[j].indices.sumOf{i->w1[j][i]*x[i]}};val h1=DoubleArray(hidden1){relu(z1[it])};val z2=DoubleArray(hidden2){j->b2[j]+w2[j].indices.sumOf{i->w2[j][i]*h1[i]}};val h2=DoubleArray(hidden2){relu(z2[it])};val y=DoubleArray(outputSize){j->sigmoid(b3[j]+w3[j].indices.sumOf{i->w3[j][i]*h2[i]})};return F(x,z1,h1,z2,h2,y)}
 fun trainSample(x:DoubleArray,winning:Set<Int>,lr:Double,l2:Double){val f=forward(x);val d3=DoubleArray(outputSize){j->f.y[j]-if(j+1 in winning)1.0 else 0.0};val d2=DoubleArray(hidden2){i->var q=0.0;for(j in 0 until outputSize)q+=w3[j][i]*d3[j];if(f.z2[i]>0)q else 0.0};val d1=DoubleArray(hidden1){i->var q=0.0;for(j in 0 until hidden2)q+=w2[j][i]*d2[j];if(f.z1[i]>0)q else 0.0};for(j in 0 until outputSize){for(i in 0 until hidden2)w3[j][i]-=lr*(d3[j]*f.h2[i]+l2*w3[j][i]);b3[j]-=lr*d3[j]};for(j in 0 until hidden2){for(i in 0 until hidden1)w2[j][i]-=lr*(d2[j]*f.h1[i]+l2*w2[j][i]);b2[j]-=lr*d2[j]};for(j in 0 until hidden1){for(i in 0 until inputSize)w1[j][i]-=lr*(d1[j]*f.x[i]+l2*w1[j][i]);b1[j]-=lr*d1[j]}}
 fun predict(x:DoubleArray)=forward(x).y.mapIndexed{i,v->i+1 to v}.toMap()
 fun snapshot()=NeuralNetworkSnapshot(w1.map{it.copyOf()}.toTypedArray(),b1.copyOf(),w2.map{it.copyOf()}.toTypedArray(),b2.copyOf(),w3.map{it.copyOf()}.toTypedArray(),b3.copyOf())
 fun restore(s:NeuralNetworkSnapshot){for(i in w1.indices)s.w1.getOrNull(i)?.copyInto(w1[i]);s.b1.copyInto(b1);for(i in w2.indices)s.w2.getOrNull(i)?.copyInto(w2[i]);s.b2.copyInto(b2);for(i in w3.indices)s.w3.getOrNull(i)?.copyInto(w3[i]);s.b3.copyInto(b3)}
}

object NeuralModelStore{private val models=mutableMapOf<String,NeuralNetworkSnapshot>();@Synchronized fun put(name:String,s:NeuralNetworkSnapshot){models[name]=s};@Synchronized fun get(name:String)=models[name]}
