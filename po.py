#coding=utf-8
import json
import time
import requests
import urllib
import numpy as np
import re
import sys

openfalcon = 'http://127.0.0.1:8080/api/v1'

#读取json文件
jsonPath = './cfg.json'
with open(jsonPath,'r') as f:
    data=json.load(f)
#print( data )
user = data["api"]["user"]
password = data["api"]["password"]
#print "u:",user," ,p:", password

def get_sig(user=user, password=password):
    url = '%s/user/login' % openfalcon
    response = requests.post(url, headers={"Content-Type":"application/json"}, data=json.dumps({"name":user, "password":password}), timeout=2)
    #print  response.text
    return response.json()

def get_graph_history( start_time, end_time ):
    
    sig = get_sig()
    headers = {
        'Apitoken': json.dumps({'name': sig['name'], 'sig': sig['sig']}),
        'Content-type': 'application/json',
        'X-Forwarded-For': '127.0.0.1',
    }

    #=========================================================================
    # 获取 得到eids
    url  = "{}/graph/endpoint?q=.".format( openfalcon ) #, '|'.join( hostname ) )
    ret  = requests.get( url, headers=headers, timeout=30 )
    retd = dict([(iter["endpoint"], iter["id"]) for iter in ret.json() ])
    retI = retd.keys()
    retv = map( int, retd.values() ) 
    print "retd",retd, retv, retI
    eids = ','.join( str(s) for s in retv if s not in [None] )
    print "eids: ",eids
    hostname = ','.join( str(s) for s in retI if s not in [None] )
    print "hostname: ",hostname
 
    #=========================================================================
    # 获取 得到eid
    url  = "{url}/graph/endpoint_counter?eid={eids}&metricQuery={c}".format( url=openfalcon, eids=urllib.quote( eids ), c="df.bytes.free.percent" )
    ret  = requests.get( url, headers=headers, timeout=30 )

    #print "url", url,"\nret:", ret.json(), "\nmetrics: ", jsonpath( ret.json(), ".counter" )
    #print ret.json()
    counters = [
        "load.15min",
        "mem.memfree.percent",
    ] 
    for item  in ret.json():
        #print value['counter']
        value = item['counter']
        if "fstype=nfs" not in value: 
            if "/boot" not in value: 
                if value not in counters:
                    counters.append( value )


    #print "counter:", counter
    data = {
        "step"      : 60,
        "start_time": start_time,
        "end_time"  : end_time,
        "hostnames" : retI,
        "counters"  : counters,
        "consol_fun": "AVERAGE",
    }
    url      = '%s/graph/history' % openfalcon
    print data
    response = requests.post(url, headers=headers, data=json.dumps(data), timeout=30)
    
    #//hdfree_counters = [
    #//    "df.bytes.free.percent/fstype=ext4,mount=/",
    #//]
    #//data = {
    #//    "step": 3600,
    #//    "start_time": start_time,
    #//    "hostnames": [hostname],
    #//    "end_time": end_time,
    #//    "counters": hdfree_counters,
    #//    "consol_fun": "AVERAGE"
    #//}
    #//hdfree_response = requests.post(url, headers=headers, data=json.dumps(data))
    #//
    #//return json.dumps({"cpuinfo":cpuload_response.text,"hdfree":hdfree_response.text})

    # 格式化数据 
    #print data3
    data = {}
    for value in response.json():
         
        #print "gg value:", value 
	if value != "error" : 
            
            endpoint = str( value['endpoint'] )
            #counter  = value['counter']
            vmin, vmax, vavg, vcount, lab_rang = countit( value['Values'] )
            #vmax = max( value['Values'], key=lambda x: x['value'] )
            #vmin = min( value['Values'], key=lambda x: x['value'] )
            if vcount > 0:
                counter = str( value['counter'] ) #.replace( "mem.memfree.percent", "mem.free%" ) 
                #         df.bytes.free.percent/fstype=ext4,mount=
                if counter.find( "df.bytes.free.percent" ) >= 0 :
                    counter = "硬盘空间：" + counter.split('=')[-1] + "：" + lab_rang + "%"
                    if vmin < 15 :
                        counter += " **注意**"
                elif counter == "load.15min":
                    counter = "系统负载：" + lab_rang 
                    if vmax > 4 :
                        counter += " **注意**"
                elif counter == "mem.memfree.percent":
                    counter = "内存空间：" + lab_rang + "%"
                    if vmin <= 10 :
                        counter += " **注意**"
               
                #tem = { 'endpoint':value['endpoint'],'counter':counter,'count':vcount }
                if data.has_key( endpoint ):
                    data[ endpoint ] += counter + "\n"
                else:
                    data[ endpoint ]  = counter + "\n"
    
    text = ""
    for key,value in data.items():
        text += "# 服务器：" + key + "\n" + value + "\n---\n"
    text = text.rstrip().rstrip("\n").rstrip("-").rstrip("\n").rstrip() #.replace( "-# 服务器", "# 服务器" )
    
    #print '得到指定监控项的历史记录:', data
    url  = "http://127.0.0.1:4000/sender/mail"
    data = {
	"tos": "lekj@qq.com",
	"subject": "服务器日常报告 " + time.strftime("%Y-%m-%d %H:%M", time.localtime()) ,
	"content": text 
    } 
    ret  = requests.post( url, data=data, timeout=30 )
    #print ret.text


    #/api/v1/user/name/
    #=========================================================================
    # 获取用户信息 
    url  = "{url}/user/name/{name}".format( url=openfalcon, name=user )
    ret  = requests.get( url, headers=headers, timeout=30 )
    #print ret
    info = ret.json();
    #print info["im"]
   
    if info["im"] != "" : 
        url  = "http://127.0.0.1:23329/api/v1/message"
        data = {
    	    "tos": info["im"],
    	    "subject": "日常报告 " + time.strftime("%Y-%m-%d %H:%M", time.localtime()) ,
    	    "content": text 
        } 
        ret  = requests.post( url, data=data, timeout=30 )
        print ret.text
    
    return "Done"

def countit( in_value ):
    vcount = 0
    arr    = [] 
    for item in in_value:
        if item['value'] is not None :
            vcount += 1
            #print  float( item['value'] ) 
            arr.append( float( item['value'] ) )
    if arr:
        vmin = min( arr )
        vmax = max( arr )
        vavg = np.mean( arr )  
    else:
        vmin = vmax = vavg = 0
    #print vmin, '~', vmax, ' - ', vcount
    if vmin == vmax:
        lab_rang = "{:.2f}".format( vmin )
    else:
        lab_rang = "{:.2f}~{:.2f}".format( vmin, vmax )
    
    return vmin, vmax, vavg, vcount, lab_rang


if __name__ == '__main__':

    end_time   = int(time.time())
    #start_time = end_time - 86400
    start_time = end_time - 86400

    print get_graph_history( start_time, end_time )


