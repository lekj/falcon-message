######## #!/usr/local/python-2.7/bin/python2.7
#coding=utf-8
import json
import time
import requests
import urllib
import numpy as np
import re
import sys
import os

openfalcon = 'http://127.0.0.1:8080/api/v1'

def get_sig(user, password):
    url = '%s/user/login' % openfalcon
    response = requests.post(url, headers={"Content-Type":"application/json"}, data=json.dumps({"name":user, "password":password}), timeout=2)
    #print  response.text
    return response.json()

def get_graph_history( start_time, end_time ):

    #读取json文件
    jsonPath = os.path.split(os.path.realpath(__file__))[0] + '/cfg.json'
    #jsonPath = '.'+'/cfg.json'
    with open(jsonPath,'r') as f:
        data=json.load(f)
    #print( data )
    user = data["api"]["user"]
    password = data["api"]["password"]
    #print "u:",user," ,p:", password
    
    sig = get_sig( user, password )
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
        "load.p15min",
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
    print "post data: ", data
    response = requests.post(url, headers=headers, data=json.dumps(data), timeout=40)
    
 
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

    # 格式化数据 邮件和钉钉！
    #print data3
    data = {}
    data_wx = {}
    for value in response.json():
        #print "gg value:", value
        if value != "error" :
            endpoint = str( value['endpoint'] )
            #counter  = value['counter']
            vmin, vmax, vavg, vcount, lab_rang, lab_rang_wx = countit( value['Values'] )
            #vmax = max( value['Values'], key=lambda x: x['value'] )
            #vmin = min( value['Values'], key=lambda x: x['value'] )
            if vcount > 0:
                ocounter = str( value['counter'] )
                counter_wx = ""
                if ocounter.find( "df.bytes.free.percent" ) >= 0 :
                    counter = "- 硬盘空间：" + ocounter.split('=')[-1] + "：" + lab_rang + "%"
                    if vmin < 15 :
                        counter += " **注意**"
                        counter_wx = "P:" + ocounter.split('=')[-1] + ":" + lab_rang_wx + "% !"
                elif ocounter == "load.p15min":
                    counter = "- 系统负载：" + lab_rang + "%"
                    counter_wx = "L:" + lab_rang_wx + "%"
                    if vmax >= 85 :
                        counter += " **注意**"
                        counter_wx += " !"
                elif ocounter == "mem.memfree.percent":
                    counter = "- 内存空间：" + lab_rang + "%"
                    if vmin < 10 :
                        counter += " **注意**"
                        counter_wx = "M:" + lab_rang_wx + "% !"
               
                #tem = { 'endpoint':value['endpoint'],'counter':counter,'count':vcount }
                if data.has_key( endpoint ):
                    data[ endpoint ] += counter + "\n"
                else:
                    data[ endpoint ]  = counter + "\n"

                if( counter_wx != "" ) :
                    if data_wx.has_key( endpoint ):
                        data_wx[ endpoint ] += counter_wx + "\n"
                    else:
                        data_wx[ endpoint ]  = counter_wx + "\n"

    text = ""
    for key,value in data.items():
        text += "# 主机：" + key + "\n" + value + "---\n"
    text = text.rstrip().rstrip("\n").rstrip("-").rstrip("\n").rstrip() #.replace( "-# 服务器", "# 服务器" )

    text_wx = ""
    for key,value in data_wx.items():
        text_wx += "S=" + key + "\n" + value + "\n"
    text_wx = text_wx.rstrip().rstrip("\n").rstrip("-").rstrip("\n").rstrip() #.replace( "-# 服务器", "# 服务器" )

    #print '得到指定监控项的历史记录:', data
    url  = "http://127.0.0.1:4000/sender/mail"
    data = {
	    "tos": "lekj@qq.com",
	    "subject": "服务器日常报告 " + time.strftime("%Y-%m-%d %H:%M", time.localtime()) ,
	    "content": text
    } 
    ret  = requests.post( url, data=data, timeout=30 )
    print "mail back:", ret.text


    #/api/v1/user/name/
    #=========================================================================
    # 获取用户信息 
    url  = "{url}/user/name/{name}".format( url=openfalcon, name=user )
    ret  = requests.get( url, headers=headers, timeout=30 )
    #print ret
    info = ret.json()
    #print info["im"]
   
    if info["im"] != "" : 
        url  = "http://127.0.0.1:23329/api/v1/message"
        data = {
    	    "tos": info["im"],
    	    "subject": "服务器报告 " + time.strftime("%m-%d %H:%M", time.localtime()) ,
    	    "content": "## 服务器报告 " + time.strftime("%Y-%m-%d %H:%M", time.localtime()) + "\n" + text,
    	    "content_wx": text_wx
        } 
        ret  = requests.post( url, data=data, timeout=30 )
        print "im back:", ret.text
    
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
        lab_rang = "{:.2f}".format( vmax )
        lab_rang_wx = "{:.1f}".format( vmax )
    elif vmax-vmin < 1: 
        lab_rang = "{:.2f}~{:.2f}｜{:.2f}".format( vmin, vmax, vavg )
        lab_rang_wx = "+{:.1f}".format( vmax )
    else:
        lab_rang = "{:.2f}~{:.2f}｜{:.2f}".format( vmin, vmax, vavg )
        lab_rang_wx = "{:.1f}~{:.1f}｜{:.1f}".format( vmin, vmax, vavg )
    return vmin, vmax, vavg, vcount, lab_rang, lab_rang_wx

if __name__ == '__main__':

    end_time   = int(time.time())
    #start_time = end_time - 86400
    start_time = end_time - 86400
    print "start: " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    print get_graph_history( start_time, end_time )


